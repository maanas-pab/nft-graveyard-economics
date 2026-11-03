/* app.js — the timeline, the readouts, and the render loop.
 *
 * Everything the page shows is derived from window.GARDEN (produced by
 * `python3 -m src.pipeline --web`). No hardcoded numbers: scrub the
 * slider and every readout, card, and flower recomputes from the data.
 */
(function () {
  'use strict';

  var G = window.GARDEN;
  var canvas = document.getElementById('garden');
  if (!G || !canvas) return;

  var ctx = canvas.getContext('2d');

  /* ------------------------------------------------------------------ *
   * constants — mirror src/plates.py's cell geometry
   * ------------------------------------------------------------------ */

  var W = 1340, H = 560;
  var PAD = 40, GAP = 16;
  var HEADER = 64, CELL_H = 392;
  var CELL_W = (W - PAD * 2 - GAP * 4) / 5;
  var CELL_TOP = HEADER;
  var CAP_RULE = CELL_TOP + CELL_H + 10;   /* 466 */
  var PROGRESS_Y = H - 10;                 /* 550 */

  var ORDER = ['punks', 'bayc', 'azuki', 'doodles', 'moonbirds'];
  var MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June',
                     'July', 'August', 'September', 'October', 'November',
                     'December'];
  var MONTH_ABBR = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
                    'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];

  var INK = '#3a3026';
  var FAINT = '#8c7e6c';
  var RULE = '#bcaea6';
  var ALERT = '#b0412a';
  var GOLD = '#b07626';
  var PLANTED = 'rgb(196,186,168)';

  var MONTHS = G.months;
  var N = MONTHS.length;
  var LAST = N - 1;
  var BASE_MS = 110;              /* ms per month at 1x */

  /* ------------------------------------------------------------------ *
   * static data derived once
   * ------------------------------------------------------------------ */

  var COLL = {};
  G.collections.forEach(function (c) { COLL[c.symbol] = c; });

  /* running all-time high per collection (for bloom size + ATH label) */
  var ATH = {};
  var SEED = {};
  ORDER.forEach(function (sym) {
    var floors = G.series[sym].floor_eth;
    var run = 0, arr = [];
    for (var i = 0; i < N; i++) {
      if (floors[i] != null && floors[i] > run) run = floors[i];
      arr.push(run > 0 ? run : null);
    }
    ATH[sym] = arr;
    SEED[sym] = sym.split('').reduce(function (a, c) {
      return a + c.charCodeAt(0);
    }, 0);
  });

  var PEAK_USD = Math.max.apply(null, G.totals.market_usd);
  var PEAK_IDX = G.totals.market_usd.indexOf(PEAK_USD);
  var LAST_USD = G.totals.market_usd[LAST];
  var DESTROYED_PCT = (PEAK_USD - LAST_USD) / PEAK_USD * 100;

  /* ------------------------------------------------------------------ *
   * formatting
   * ------------------------------------------------------------------ */

  function fmtUsd(v) {
    if (v == null) return '—';
    if (v >= 1e9) return '$' + (v / 1e9).toFixed(2) + 'B';
    if (v >= 1e6) return '$' + (v / 1e6).toFixed(1) + 'M';
    if (v >= 1e3) return '$' + Math.round(v / 1e3) + 'K';
    return '$' + Math.round(v);
  }

  function fmtEth(v) {
    if (v == null) return '—';
    return (v >= 100 ? v.toFixed(1) : v.toFixed(2)) + ' ETH';
  }

  function fmtPct(v, digits) {
    if (v == null) return '—';
    var d = digits == null ? 1 : digits;
    return (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(d) + '%';
  }

  function monthLabel(key) {
    var p = key.split('-');
    return MONTH_NAMES[+p[1] - 1] + ' ' + p[0];
  }

  function monthStamp(key) {
    var p = key.split('-');
    return MONTH_ABBR[+p[1] - 1] + ' ' + p[0];
  }

  /* ------------------------------------------------------------------ *
   * state at a (possibly fractional) position on the timeline
   * ------------------------------------------------------------------ */

  function lerp(a, b, t) { return a + (b - a) * t; }

  function valueAt(arr, i, f) {
    var a = arr[i];
    var b = arr[Math.min(i + 1, LAST)];
    if (a == null) return null;
    if (b == null) return a;
    return lerp(a, b, f);
  }

  function stateAt(sym, pos) {
    var i = Math.min(Math.floor(pos), LAST);
    var f = Math.min(pos - i, 1);
    var s = G.series[sym];
    var price = valueAt(s.floor_eth, i, f);
    if (price == null) return null;                 /* not planted yet */
    var ath = valueAt(ATH[sym], i, f);
    return {
      price: price,
      ath: ath,
      usd: valueAt(s.floor_usd, i, f),
      drawdown: valueAt(s.drawdown, i, f),
      ratio: ath > 0 ? Math.min(1, price / ath) : 0
    };
  }

  /* ------------------------------------------------------------------ *
   * canvas sizing (hi-dpi)
   * ------------------------------------------------------------------ */

  function fit() {
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    dirty = true;
  }

  /* ------------------------------------------------------------------ *
   * drawing
   * ------------------------------------------------------------------ */

  var dirty = true;

  function drawCellEmpty(x, label) {
    ctx.font = '13px Georgia, "Times New Roman", serif';
    ctx.fillStyle = PLANTED;
    ctx.textAlign = 'center';
    ctx.fillText(label || 'not yet planted', x + CELL_W / 2,
                 CELL_TOP + CELL_H / 2);
    ctx.textAlign = 'start';
  }

  function drawCaption(x, sym, st) {
    /* hairline rule, as on the printed plates */
    ctx.beginPath();
    ctx.moveTo(x + CELL_W * 0.14, CAP_RULE);
    ctx.lineTo(x + CELL_W * 0.86, CAP_RULE);
    ctx.lineWidth = 1;
    ctx.strokeStyle = RULE;
    ctx.stroke();

    ctx.textAlign = 'center';

    ctx.font = '13px Georgia, "Times New Roman", serif';
    ctx.fillStyle = FAINT;
    ctx.fillText(sym.toUpperCase(), x + CELL_W / 2, CAP_RULE + 22);

    if (!st) {
      ctx.fillStyle = PLANTED;
      ctx.fillText('—', x + CELL_W / 2, CAP_RULE + 48);
      ctx.textAlign = 'start';
      return;
    }

    var dd = st.drawdown;
    var deep = dd <= -90;
    ctx.font = '17px Georgia, "Times New Roman", serif';
    ctx.fillStyle = deep ? ALERT : INK;
    ctx.fillText(fmtEth(st.price), x + CELL_W / 2, CAP_RULE + 48);

    ctx.font = '13px Georgia, "Times New Roman", serif';
    ctx.fillStyle = deep ? ALERT : (dd <= -50 ? GOLD : FAINT);
    ctx.fillText(dd == null ? '—' : fmtPct(dd), x + CELL_W / 2,
                 CAP_RULE + 70);
    ctx.textAlign = 'start';
  }

  function draw(pos) {
    ctx.fillStyle = '#f7f2e8';
    ctx.fillRect(0, 0, W, H);

    var mi = Math.max(0, Math.min(LAST, Math.round(pos)));

    /* --- header: month stamp + hairline -------------------------------- */
    ctx.font = '26px Georgia, "Times New Roman", serif';
    ctx.fillStyle = INK;
    ctx.textAlign = 'center';
    ctx.fillText(monthStamp(MONTHS[mi]), W / 2, 36);
    ctx.textAlign = 'start';

    ctx.beginPath();
    ctx.moveTo(PAD, HEADER - 14);
    ctx.lineTo(W - PAD, HEADER - 14);
    ctx.lineWidth = 1;
    ctx.strokeStyle = RULE;
    ctx.stroke();

    /* --- five plots ------------------------------------------------------ */
    for (var c = 0; c < ORDER.length; c++) {
      var sym = ORDER[c];
      var x = PAD + c * (CELL_W + GAP);
      var st = stateAt(sym, pos);

      /* soil line under the plot */
      var groundY = CELL_TOP + CELL_H * 0.845;
      ctx.beginPath();
      ctx.moveTo(x + CELL_W * 0.06, groundY);
      ctx.lineTo(x + CELL_W * 0.94, groundY);
      ctx.lineWidth = 1;
      ctx.strokeStyle = 'rgba(188,174,166,0.55)';
      ctx.stroke();

      if (!st) {
        drawCellEmpty(x);
        drawCaption(x, sym, null);
        continue;
      }

      var meta = COLL[sym];
      var species = {
        petals: meta.petals,
        shape: meta.petal_shape,
        accent: Flower.hexToRgb(meta.accent_hex)
      };
      var bloom = Flower.bloomFor(st.price, st.ath, SEED[sym]);
      var epitaph = st.drawdown != null && st.drawdown <= -90
        ? '-' + Math.abs(Math.round(st.drawdown)) + '%' : null;

      ctx.save();
      ctx.beginPath();
      ctx.rect(x, CELL_TOP, CELL_W, CELL_H);
      ctx.clip();
      ctx.translate(x, CELL_TOP);
      Flower.renderFlower(ctx, [CELL_W, CELL_H], species, bloom,
                          SEED[sym], epitaph);
      ctx.restore();

      drawCaption(x, sym, st);
    }

    /* --- progress hairline ----------------------------------------------- */
    ctx.beginPath();
    ctx.moveTo(PAD, PROGRESS_Y);
    ctx.lineTo(W - PAD, PROGRESS_Y);
    ctx.lineWidth = 2;
    ctx.strokeStyle = RULE;
    ctx.stroke();

    var progX = PAD + (W - PAD * 2) * (pos / LAST);
    ctx.beginPath();
    ctx.moveTo(PAD, PROGRESS_Y);
    ctx.lineTo(progX, PROGRESS_Y);
    ctx.lineWidth = 2;
    ctx.strokeStyle = INK;
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(progX, PROGRESS_Y, 4, 0, Math.PI * 2);
    ctx.fillStyle = INK;
    ctx.fill();
  }

  /* ------------------------------------------------------------------ *
   * DOM: readouts
   * ------------------------------------------------------------------ */

  var roMonth = document.getElementById('ro-month');
  var roValue = document.getElementById('ro-value');
  var roDestroyed = document.getElementById('ro-destroyed');
  var roEth = document.getElementById('ro-eth');
  var scrub = document.getElementById('scrub');
  var playBtn = document.getElementById('play');
  var ticksEl = document.getElementById('ticks');
  var eventsEl = document.getElementById('events');
  var cardsEl = document.getElementById('cards');
  var statsEl = document.getElementById('stats');

  function updateReadouts(pos) {
    var mi = Math.max(0, Math.min(LAST, Math.round(pos)));
    roMonth.textContent = monthLabel(MONTHS[mi]);
    roValue.textContent = fmtUsd(G.totals.market_usd[mi]);
    var destroyed = G.totals.destroyed_usd[mi] / PEAK_USD * 100;
    roDestroyed.textContent = destroyed.toFixed(1) + '%';
    roEth.textContent = '$' + Math.round(G.eth_usd[mi]).toLocaleString('en-US');
    if (+scrub.value !== mi) scrub.value = mi;
    scrub.setAttribute('aria-valuetext', monthLabel(MONTHS[mi]));
    highlightEvent(mi);
  }

  /* ------------------------------------------------------------------ *
   * DOM: year ticks along the track
   * ------------------------------------------------------------------ */

  function buildTicks() {
    var html = '';
    for (var year = 2021; year <= 2026; year++) {
      var idx = MONTHS.indexOf(year + '-01');
      if (idx < 0) continue;
      var pct = idx / LAST;
      html += '<span class="tick" style="left:calc(10px + ' + pct +
              ' * (100% - 20px))">' + year + '</span>';
    }
    ticksEl.innerHTML = html;
  }

  /* ------------------------------------------------------------------ *
   * DOM: event chips
   * ------------------------------------------------------------------ */

  function buildEvents() {
    var html = '';
    G.events.forEach(function (e, i) {
      var idx = MONTHS.indexOf(e.date);
      html += '<button class="event" data-kind="' + e.kind +
              '" data-idx="' + idx + '" data-i="' + i + '" ' +
              'title="' + monthLabel(e.date) + '">' + e.label + '</button>';
    });
    eventsEl.innerHTML = html;
    eventsEl.addEventListener('click', function (ev) {
      var btn = ev.target.closest('.event');
      if (!btn) return;
      var idx = +btn.dataset.idx;
      if (idx < 0) return;
      pause();
      pos = idx;
      dirty = true;
    });
  }

  function highlightEvent(mi) {
    var chips = eventsEl.children;
    for (var i = 0; i < chips.length; i++) {
      chips[i].classList.toggle('is-on', +chips[i].dataset.idx === mi);
    }
  }

  /* ------------------------------------------------------------------ *
   * DOM: per-collection cards
   * ------------------------------------------------------------------ */

  var cards = {};

  function buildCards() {
    var html = '';
    ORDER.forEach(function (sym) {
      var meta = COLL[sym];
      var ath = Math.max.apply(null,
        G.series[sym].floor_eth.filter(function (v) { return v != null; }));
      html +=
        '<div class="card" data-sym="' + sym + '">' +
          '<div class="card-name">' +
            '<span class="swatch" style="background:' + meta.accent_hex +
            '"></span>' + sym.toUpperCase() + '</div>' +
          '<div class="card-floor">—</div>' +
          '<div class="card-usd">not planted</div>' +
          '<div class="card-dd">—</div>' +
          '<div class="card-bar" style="color:' + meta.accent_hex +
            '"><i style="width:0%"></i></div>' +
          '<div class="card-ath">ATH ' + fmtEth(ath) + '</div>' +
        '</div>';
    });
    cardsEl.innerHTML = html;
    ORDER.forEach(function (sym) {
      var el = cardsEl.querySelector('[data-sym="' + sym + '"]');
      cards[sym] = {
        root: el,
        floor: el.querySelector('.card-floor'),
        usd: el.querySelector('.card-usd'),
        dd: el.querySelector('.card-dd'),
        bar: el.querySelector('.card-bar > i')
      };
    });
  }

  function updateCards(pos) {
    ORDER.forEach(function (sym) {
      var c = cards[sym];
      var st = stateAt(sym, pos);
      if (!st) {
        c.floor.textContent = '—';
        c.floor.style.color = '';
        c.usd.textContent = 'not planted';
        c.dd.textContent = '—';
        c.dd.style.color = FAINT;
        c.bar.style.width = '0%';
        return;
      }
      var dd = st.drawdown;
      var deep = dd <= -90;
      c.floor.textContent = fmtEth(st.price);
      c.floor.style.color = deep ? ALERT : '';
      c.usd.textContent = fmtUsd(st.usd) + ' · ' +
        (st.ratio * 100).toFixed(0) + '% of ATH';
      c.dd.textContent = dd == null ? '—' : fmtPct(dd);
      c.dd.style.color = deep ? ALERT : (dd <= -50 ? GOLD : FAINT);
      c.bar.style.width = (st.ratio * 100).toFixed(1) + '%';
    });
  }

  /* ------------------------------------------------------------------ *
   * DOM: stats — computed from the payload, never hardcoded
   * ------------------------------------------------------------------ */

  function worstDrawdown() {
    var worst = { pct: 0, sym: null };
    ORDER.forEach(function (sym) {
      var dds = G.series[sym].drawdown.filter(function (v) { return v != null; });
      var min = Math.min.apply(null, dds);
      if (min < worst.pct) worst = { pct: min, sym: sym };
    });
    return worst;
  }

  function buildStats() {
    var peakEth = G.totals.market_eth[PEAK_IDX];
    var lastEth = G.totals.market_eth[LAST];
    var worst = worstDrawdown();
    var below90 = ORDER.filter(function (sym) {
      return Math.min.apply(null,
        G.series[sym].drawdown.filter(function (v) { return v != null; })) <= -90;
    }).length;

    var stats = [
      { num: fmtUsd(PEAK_USD), label: 'Combined floor value, ' +
          monthLabel(MONTHS[PEAK_IDX]),
        sub: (peakEth / 1e6).toFixed(2) + 'M ETH at the top' },
      { num: fmtUsd(LAST_USD), label: 'Today (' + monthLabel(MONTHS[LAST]) + ')',
        sub: Math.round(lastEth / 1000) + 'K ETH left' },
      { num: '−' + DESTROYED_PCT.toFixed(1) + '%', alert: true,
        label: 'Peak to today',
        sub: fmtUsd(PEAK_USD - LAST_USD) + ' erased from floor value' },
      { num: fmtPct(worst.pct), label: 'Deepest drawdown',
        sub: (worst.sym || '').toUpperCase() + ', from its own ATH' },
      { num: below90 + ' of 5', label: 'Below −90%',
        sub: 'every blue chip crossed the line' },
      { num: N + ' months', label: 'Observed',
        sub: monthLabel(MONTHS[0]) + ' → ' + monthLabel(MONTHS[LAST]) }
    ];

    statsEl.innerHTML = stats.map(function (s) {
      return '<div class="stat">' +
        '<div class="stat-num' + (s.alert ? ' alert' : '') + '">' + s.num +
        '</div>' +
        '<div class="stat-label">' + s.label + '</div>' +
        '<div class="stat-sub">' + s.sub + '</div>' +
      '</div>';
    }).join('');
  }

  /* ------------------------------------------------------------------ *
   * playback
   * ------------------------------------------------------------------ */

  var pos = 0;
  var playing = false;
  var speedDiv = 1;             /* data-speed: 2 => 0.5x, 0.5 => 2x */
  var lastT = 0;
  var dragging = false;

  function setPlaying(on) {
    playing = on;
    playBtn.textContent = on ? '⏸' : '▶';
    playBtn.classList.toggle('is-playing', on);
    playBtn.setAttribute('aria-label', on ? 'pause the timeline'
                                          : 'play the timeline');
    lastT = 0;
  }

  function pause() { if (playing) setPlaying(false); }

  function toggle() {
    if (!playing && pos >= LAST - 0.001) pos = 0;   /* replay from the top */
    setPlaying(!playing);
    dirty = true;
  }

  function step(delta) {
    pause();
    pos = Math.max(0, Math.min(LAST, Math.round(pos) + delta));
    dirty = true;
  }

  /* ------------------------------------------------------------------ *
   * render loop
   * ------------------------------------------------------------------ */

  function render() {
    draw(pos);
    updateReadouts(pos);
    updateCards(pos);
    dirty = false;
  }

  function frame(t) {
    if (playing) {
      if (lastT === 0) lastT = t;
      var dt = Math.min(t - lastT, 250);            /* tab-switch guard */
      lastT = t;
      pos += (dt / BASE_MS) * (1 / speedDiv);
      if (pos >= LAST) {
        pos = LAST;
        setPlaying(false);
      }
      dirty = true;
    }
    if (dirty) render();
    requestAnimationFrame(frame);
  }

  /* ------------------------------------------------------------------ *
   * wiring
   * ------------------------------------------------------------------ */

  function wire() {
    playBtn.addEventListener('click', toggle);

    scrub.addEventListener('pointerdown', function () { dragging = true; });
    window.addEventListener('pointerup', function () { dragging = false; });
    scrub.addEventListener('input', function () {
      pause();
      pos = +scrub.value;
      dirty = true;
    });

    document.querySelectorAll('.speed').forEach(function (btn) {
      btn.addEventListener('click', function () {
        document.querySelectorAll('.speed').forEach(function (b) {
          b.classList.remove('is-on');
        });
        btn.classList.add('is-on');
        speedDiv = parseFloat(btn.dataset.speed);
      });
    });

    document.addEventListener('keydown', function (e) {
      var tag = (e.target.tagName || '').toLowerCase();
      var interactive = tag === 'input' || tag === 'button' || tag === 'a';
      if (e.code === 'Space' && !interactive) {
        e.preventDefault();
        toggle();
      } else if (e.key === 'ArrowRight' && !interactive) {
        e.preventDefault();
        step(1);
      } else if (e.key === 'ArrowLeft' && !interactive) {
        e.preventDefault();
        step(-1);
      } else if (e.key === 'Home' && !interactive) {
        e.preventDefault();
        pause();
        pos = 0; dirty = true;
      } else if (e.key === 'End' && !interactive) {
        e.preventDefault();
        pause();
        pos = LAST; dirty = true;
      }
    });

    window.addEventListener('resize', fit);
  }

  /* ------------------------------------------------------------------ *
   * boot — open on April 2022, the top of the bubble: the story starts
   * where the money was.
   * ------------------------------------------------------------------ */

  /* deep link: #2024-01 opens the garden at that month, so any moment in
   * the crash can be shared as a URL */
  function posFromHash() {
    var m = /^#(\d{4})-(\d{2})$/.exec(location.hash || '');
    if (!m) return -1;
    return MONTHS.indexOf(m[1] + '-' + m[2]);
  }

  function boot() {
    buildTicks();
    buildEvents();
    buildCards();
    buildStats();
    wire();
    fit();
    pos = posFromHash();
    if (pos < 0) pos = MONTHS.indexOf('2022-04');
    if (pos < 0) pos = 0;
    if (location.hash === '#play') {              /* #play: auto-start */
      pos = 0;
      setPlaying(true);
    }
    scrub.max = LAST;
    scrub.value = pos;
    render();                       /* paint synchronously: never show a
                                       blank garden, even before the first
                                       animation frame */
    requestAnimationFrame(frame);
  }

  boot();
})();
