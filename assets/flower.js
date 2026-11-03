/* flower.js — canvas port of src/flower.py.
 *
 * Same parametric maths as the Python/Pillow renderer that prints the
 * specimen plates, so the live garden and the printed plates can never
 * disagree about what a given price does to a flower:
 *
 *   floor / running ATH -> bloom radius (log-scaled), droop angle,
 *                          petal shed count, saturation/value, stem lean
 *
 * The only difference is the RNG: Python's random.Random(seed) is a
 * Mersenne Twister, here we use mulberry32. Both are deterministic per
 * seed — the jitter (initial petal angle, fallen-petal placement) just
 * doesn't bit-match between mediums, which is fine: it's decoration,
 * not data.
 */
(function (global) {
  'use strict';

  var TAU = Math.PI * 2;
  var DEAD_LEAF = [122, 104, 78];
  var GREEN_LIVE = [94, 126, 74];
  var GREEN_DEAD = [116, 102, 76];

  /* ------------------------------------------------------------------ *
   * colour — direct ports of colorsys.rgb_to_hls / hls_to_rgb and the
   * _shade/_mix helpers from flower.py.
   * ------------------------------------------------------------------ */

  function hexToRgb(hex) {
    var h = String(hex).replace('#', '');
    return [
      parseInt(h.slice(0, 2), 16),
      parseInt(h.slice(2, 4), 16),
      parseInt(h.slice(4, 6), 16)
    ];
  }

  function mix(a, b, t) {
    return [
      a[0] + (b[0] - a[0]) * t,
      a[1] + (b[1] - a[1]) * t,
      a[2] + (b[2] - a[2]) * t
    ];
  }

  function css(c) {
    return 'rgb(' + Math.round(c[0]) + ',' + Math.round(c[1]) + ',' +
           Math.round(c[2]) + ')';
  }

  function rgbToHls(r, g, b) {
    var maxc = Math.max(r, g, b);
    var minc = Math.min(r, g, b);
    var sumc = maxc + minc;
    var rangec = maxc - minc;
    var l = sumc / 2.0;
    if (minc === maxc) return [0.0, l, 0.0];
    var s = l <= 0.5 ? rangec / sumc : rangec / (2.0 - maxc - minc);
    var rc = (maxc - r) / rangec;
    var gc = (maxc - g) / rangec;
    var bc = (maxc - b) / rangec;
    var h = r === maxc ? bc - gc
          : g === maxc ? 2.0 + rc - bc
          : 4.0 + gc - rc;
    h = (h / 6.0) % 1.0;
    if (h < 0) h += 1.0;
    return [h, l, s];
  }

  function hlsChannel(m1, m2, v) {
    if (v < 0) v += 1;
    if (v > 1) v -= 1;
    if (v < 1 / 6) return m1 + (m2 - m1) * 6 * v;
    if (v < 1 / 2) return m2;
    if (v < 2 / 3) return m1 + (m2 - m1) * (2 / 3 - v) * 6;
    return m1;
  }

  function hlsToRgb(h, l, s) {
    if (s === 0) return [l, l, l];
    var m2 = l <= 0.5 ? l * (1.0 + s) : l + s - l * s;
    var m1 = 2.0 * l - m2;
    return [
      hlsChannel(m1, m2, h + 1 / 3),
      hlsChannel(m1, m2, h),
      hlsChannel(m1, m2, h - 1 / 3)
    ];
  }

  /* desaturate + darken + rot toward dead-leaf brown */
  function shade(rgb, sat, val, decay) {
    var hls = rgbToHls(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255);
    var h = hls[0];
    var l = hls[1] * (0.35 + 0.65 * val);
    var s = hls[2] * sat;
    var out = hlsToRgb(h, l, s).map(function (c) { return Math.trunc(c * 255); });
    return out.map(function (o, i) {
      return Math.trunc(o + (DEAD_LEAF[i] - o) * decay);
    });
  }

  /* ------------------------------------------------------------------ *
   * deterministic RNG (mulberry32) — stands in for random.Random(seed)
   * ------------------------------------------------------------------ */

  function rng(seed) {
    var a = seed >>> 0;
    return function () {
      a = (a + 0x6D2B79F5) >>> 0;
      var t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  /* Python's round() is banker's rounding; match it so shed counts agree */
  function pyRound(x) {
    var fl = Math.floor(x);
    var frac = x - fl;
    if (frac === 0.5) return fl % 2 === 0 ? fl : fl + 1;
    return Math.round(x);
  }

  /* ------------------------------------------------------------------ *
   * the bloom state: what the price says to the flower
   * ------------------------------------------------------------------ */

  function bloomFor(price, ath, seed) {
    var ratio = ath > 0 ? Math.min(1, Math.max(0, price / ath)) : 0;
    var logSpan = ath > 0 ? Math.log1p(ath) : 1;
    var size = 0.085 + 0.115 * (Math.log1p(Math.max(0, price)) / logSpan);
    var droop = Math.pow(1 - ratio, 1.15);
    var shedFrac = Math.pow(Math.max(0, (0.55 - ratio) / 0.55), 1.4);
    return {
      ratio: ratio,
      size: size,
      droop: droop,
      shed: shedFrac,
      saturation: 0.18 + 0.82 * Math.pow(ratio, 0.65),
      value: 0.30 + 0.70 * Math.pow(ratio, 0.55),
      lean: droop * ((seed % 2) ? 0.16 : -0.16)
    };
  }

  /* ------------------------------------------------------------------ *
   * geometry
   * ------------------------------------------------------------------ */

  /* petal in local space: base at origin, tip up +y */
  function petalPoly(length, width, shape, samples) {
    samples = samples || 22;
    var left = [], right = [];
    for (var i = 0; i <= samples; i++) {
      var t = i / samples;
      var w;
      if (shape === 'round') {
        w = width * Math.pow(Math.sin(Math.PI * Math.pow(t, 0.78)), 0.9);
      } else if (shape === 'pointed') {
        w = width * Math.pow(Math.sin(Math.PI * t), 1.55);
      } else if (shape === 'blocky') {
        var level = Math.round(t * 4) / 4;
        w = width * (level < 0.78 ? 0.98 : (level < 1.0 ? 0.6 : 0.0));
      } else {
        w = width * Math.sin(Math.PI * t);
      }
      var y = length * t;
      left.push([-w, y]);
      right.push([w, y]);
    }
    right.reverse();
    return left.concat(right);
  }

  function rot(pts, ang) {
    var c = Math.cos(ang), s = Math.sin(ang);
    return pts.map(function (p) {
      return [p[0] * c - p[1] * s, p[0] * s + p[1] * c];
    });
  }

  function tracePath(ctx, pts, ox, oy) {
    ctx.beginPath();
    ctx.moveTo(pts[0][0] + ox, pts[0][1] + oy);
    for (var i = 1; i < pts.length; i++) {
      ctx.lineTo(pts[i][0] + ox, pts[i][1] + oy);
    }
    ctx.closePath();
  }

  /* rounded rectangle without relying on ctx.roundRect */
  function roundRect(ctx, x, y, w, h, r) {
    r = Math.min(r, w / 2, h / 2);
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.arcTo(x + w, y, x + w, y + r, r);
    ctx.lineTo(x + w, y + h - r);
    ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
    ctx.lineTo(x + r, y + h);
    ctx.arcTo(x, y + h, x, y + h - r, r);
    ctx.lineTo(x, y + r);
    ctx.arcTo(x, y, x + r, y, r);
    ctx.closePath();
  }

  /* ------------------------------------------------------------------ *
   * rendering — draws into ctx at cell-local coordinates (0,0)-(w,h).
   * The caller is responsible for translating/scaling.
   * ------------------------------------------------------------------ */

  function renderFlower(ctx, cell, species, bloom, seed, epitaph) {
    var w = cell[0], h = cell[1];
    var rnd = rng(seed);

    var groundY = h * 0.845;
    var cx = w * (0.5 + bloom.lean);
    var cy = h * (0.30 + 0.26 * bloom.droop);
    var R = bloom.size * w;

    var decay = 1 - bloom.ratio;
    var petalC = shade(species.accent, bloom.saturation, bloom.value, decay * 0.72);
    var petalHi = mix(petalC, [255, 250, 240], 0.30);
    var petalLo = mix(petalC, [0, 0, 0], 0.28);
    var stemC = mix(GREEN_LIVE, GREEN_DEAD, Math.pow(decay, 0.7));

    /* --- shadow ------------------------------------------------------- */
    var shR = R * (0.9 - 0.5 * bloom.droop);
    ctx.beginPath();
    ctx.ellipse(cx, groundY, shR, shR * 0.16, 0, 0, TAU);
    ctx.fillStyle = 'rgba(60,45,30,' +
      ((46 + 60 * bloom.ratio) / 255).toFixed(3) + ')';
    ctx.fill();

    /* --- stem: quadratic bezier from soil to head ---------------------- */
    var sx = w * 0.5, sy = groundY;
    var bow = (cx - sx) * 0.35 + w * 0.10 * bloom.lean * 4;
    var ctrlX = sx + bow * 0.4;
    var ctrlY = sy - (sy - cy) * 0.55;
    var steps = 40, stemPts = [];
    for (var i = 0; i <= steps; i++) {
      var t = i / steps;
      stemPts.push([
        (1 - t) * (1 - t) * sx + 2 * (1 - t) * t * ctrlX + t * t * cx,
        (1 - t) * (1 - t) * sy + 2 * (1 - t) * t * ctrlY + t * t * cy
      ]);
    }
    var stemW = Math.max(2, w * (0.020 + 0.016 * bloom.ratio));
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.beginPath();
    ctx.moveTo(stemPts[0][0], stemPts[0][1]);
    for (i = 1; i < stemPts.length; i++) ctx.lineTo(stemPts[i][0], stemPts[i][1]);
    ctx.lineWidth = stemW;
    ctx.strokeStyle = css(stemC);
    ctx.stroke();
    ctx.lineWidth = Math.max(1, stemW / 3);
    ctx.strokeStyle = css(mix(stemC, [255, 255, 255], 0.22));
    ctx.stroke();

    /* --- one leaf, drooping with the rest ------------------------------ */
    var lt = 0.42;
    var lp = stemPts[Math.floor(lt * steps)];
    var leafLen = R * (1.05 - 0.45 * bloom.droop);
    var leafBase = petalPoly(leafLen, leafLen * 0.30, 'pointed');
    var leafPts = rot(leafBase, (58 + 42 * bloom.droop) * Math.PI / 180)
      .map(function (p) {
        var g = bloom.droop * leafLen * 0.55 *
                Math.pow(Math.abs(p[1]) / leafLen, 2);
        return [lp[0] + p[0], lp[1] + p[1] + g];
      });
    tracePath(ctx, leafPts, 0, 0);
    ctx.fillStyle = css(mix(stemC, [200, 220, 160], 0.35));
    ctx.fill();

    /* --- petals: outer ring, then inner; shed ones lie on the soil ------ */
    var n = species.petals;
    var total = 2 * n;
    var shedN = pyRound(total * bloom.shed);
    var step = shedN ? Math.ceil(total / shedN) : total + 1;
    var shed = {};
    if (shedN) {
      for (var k = 0; k < total; k += step) shed[(k % n) + '|' + Math.floor(k / n)] = true;
    }

    var angle0 = rnd() * TAU;
    var rings = [[1.0, 0.0, 0.0], [0.62, Math.PI / n, 0.18]];
    for (var ring = 0; ring < 2; ring++) {
      var scale = rings[ring][0];
      var ringOff = rings[ring][1];
      var depth = rings[ring][2];
      for (var pi = 0; pi < n; pi++) {
        var ang = angle0 + ringOff + pi * TAU / n;
        var length = R * scale * (0.86 + 0.22 * bloom.ratio);
        var width = length * (species.shape !== 'pointed' ? 0.42 : 0.34);
        var poly = petalPoly(length, width, species.shape);

        /* rotate so the tip faces outward, then gravity in screen space */
        var local = rot(poly, ang - Math.PI / 2).map(function (p) {
          return [p[0],
                  p[1] + bloom.droop * R * 1.35 * Math.pow(p[1] / length, 2)];
        });

        var fill = mix(ring === 0 ? petalLo : petalC, petalHi,
                       0.18 + 0.5 * ((pi * 37 + ring * 11) % 7) / 7);
        fill = mix(fill, DEAD_LEAF, depth + decay * 0.25);

        if (shed[pi + '|' + ring]) {
          /* re-lay it on the soil, flattened against the ground plane */
          var fx = sx + (rnd() * 0.84 - 0.42) * w * (0.4 + 0.6 * bloom.ratio);
          var fy = groundY + (rnd() * 0.057 - 0.012) * h;
          var flat = rot(poly, rnd() * 2 * Math.PI - Math.PI).map(function (p) {
            return [fx + p[0] * 1.25, fy + p[1] * 0.40];
          });
          var dead = mix(fill, DEAD_LEAF, 0.72);
          tracePath(ctx, flat, 0, 0);
          ctx.fillStyle = css(dead);
          ctx.fill();
          ctx.lineWidth = 0.7;
          ctx.strokeStyle = css(mix(dead, [60, 50, 35], 0.5));
          ctx.stroke();
          continue;
        }

        tracePath(ctx, local, cx, cy);
        ctx.fillStyle = css(fill);
        ctx.fill();
        ctx.lineWidth = 0.7;
        ctx.strokeStyle = css(mix(fill, [70, 55, 40], 0.45));
        ctx.stroke();
      }
    }

    /* --- the coin: centre disk shrinks and rusts ----------------------- */
    var coinR = R * (0.10 + 0.30 * bloom.ratio);
    var coin = mix([214, 176, 66], [118, 96, 62], Math.pow(decay, 0.8));
    ctx.beginPath();
    ctx.ellipse(cx, cy, coinR, coinR, 0, 0, TAU);
    ctx.fillStyle = css(coin);
    ctx.fill();
    ctx.lineWidth = 1.3;
    ctx.strokeStyle = css(mix(coin, [70, 55, 30], 0.5));
    ctx.stroke();
    for (var s = 0; s < 10; s++) {                      /* stipple seeds */
      var a = s * TAU / 10 + 0.3;
      var rr = coinR * 0.55;
      var r0 = Math.max(1, coinR * 0.09);
      ctx.beginPath();
      ctx.ellipse(cx + rr * Math.cos(a), cy + rr * Math.sin(a), r0, r0, 0, 0, TAU);
      ctx.fillStyle = css(mix(coin, [60, 45, 25], 0.55));
      ctx.fill();
    }

    /* --- headstone for the fully departed ------------------------------ */
    if (epitaph) {
      var stW = w * 0.30, stH = h * 0.14;
      var bx = w * 0.5 - stW / 2;
      var by = groundY - stH;
      roundRect(ctx, bx, by, stW, stH + stH * 0.18, stW * 0.30);
      ctx.fillStyle = 'rgb(168,163,154)';
      ctx.fill();
      ctx.lineWidth = 1.3;
      ctx.strokeStyle = 'rgb(110,106,99)';
      ctx.stroke();
      ctx.font = Math.round(stH * 0.30) + 'px Georgia, "Times New Roman", serif';
      ctx.fillStyle = 'rgb(70,66,60)';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(epitaph, bx + stW / 2, by + stH * 0.45);
      ctx.textAlign = 'start';
      ctx.textBaseline = 'alphabetic';
    }
  }

  /* ------------------------------------------------------------------ */

  global.Flower = {
    bloomFor: bloomFor,
    renderFlower: renderFlower,
    hexToRgb: hexToRgb,
    mix: mix
  };
})(window);
