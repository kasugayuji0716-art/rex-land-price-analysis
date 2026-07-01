const PptxGenJS = require("pptxgenjs");
const path = require("path");
const pptx = new PptxGenJS();

const OUT_DIR = "/Users/KASU/data_analysis/outputs/";
const IMG = (f) => path.join(OUT_DIR, f);

const C = {
  dark:   "0F1923",
  navy:   "1B2B4B",
  white:  "FFFFFF",
  off:    "F5F6F8",
  red:    "E8534A",
  blue:   "3A7FC1",
  gold:   "D4A843",
  gray:   "6C757D",
  lgray:  "E2E6EA",
  green:  "27AE60",
  purple: "8E44AD",
};

pptx.defineLayout({ name: "WIDE", width: 10, height: 5.625 });
pptx.layout = "WIDE";

const rect = (s, x, y, w, h, fill, lineColor, opts = {}) => {
  s.addShape(pptx.ShapeType.rect, {
    x, y, w, h,
    fill: { color: fill },
    line: { color: lineColor || fill },
    ...opts,
  });
};
const txt = (s, text, x, y, w, h, opts = {}) => {
  s.addText(text, { x, y, w, h, fontFace: "Arial", ...opts });
};
const bar = (s, color) => rect(s, 0, 0, 0.09, 5.625, color, color);

// ════════════════════════════════════════════════════════════════════════
// SLIDE 1: タイトル
// ════════════════════════════════════════════════════════════════════════
(() => {
  const s = pptx.addSlide();
  s.background = { color: C.dark };
  s.addImage({ path: IMG("corona_always_trend.png"), x: 4.2, y: 0, w: 5.8, h: 5.625, transparency: 55 });
  rect(s, 0, 0, 5.5, 5.625, "0F1923", "0F1923");

  txt(s, "コロナ禍の路線価変動", 0.5, 0.72, 5.0, 0.72,
    { fontSize: 30, bold: true, color: C.white });
  txt(s, "「次のパンデミック」でも勝てる地域を識別する", 0.5, 1.48, 5.0, 0.46,
    { fontSize: 15, color: C.gold, italic: true });
  rect(s, 0.5, 2.05, 3.8, 0.05, C.red, C.red);
  txt(s, "コロナは「フィルター」だった ─ 構造的に強い地域だけが生き残った", 0.5, 2.2, 4.8, 0.38,
    { fontSize: 11, color: "AABBCC" });
  rect(s, 0.5, 2.68, 3.8, 0.05, "334455", "334455");
  txt(s, "NII IDR REXデータセット（相続税路線価）", 0.5, 2.82, 5.0, 0.28,
    { fontSize: 11, color: "8899AA" });
  txt(s, "2018〜2022年  ·  全国230万路線  ·  空間統計分析", 0.5, 3.09, 5.0, 0.28,
    { fontSize: 11, color: "8899AA" });
  txt(s, "赤 = ずっと上昇    青 = ずっと下落", 0.5, 5.2, 5.0, 0.3,
    { fontSize: 10, color: "556677" });
})();

// ════════════════════════════════════════════════════════════════════════
// SLIDE 2: 発表の流れ
// ════════════════════════════════════════════════════════════════════════
(() => {
  const s = pptx.addSlide();
  s.background = { color: C.dark };
  txt(s, "発表の流れ", 0.4, 0.15, 9.2, 0.5,
    { fontSize: 26, bold: true, color: C.white });
  rect(s, 0.4, 0.72, 2.2, 0.05, C.blue, C.blue);

  const items = [
    { n: "01", title: "データ概要・研究目的",                    time: "3分",  color: C.blue },
    { n: "02", title: "コロナ前後の路線価変動",                  time: "5分",  color: C.gold },
    { n: "03", title: "コロナ耐性の条件 — 5タイプ分類・SHAP",   time: "5分",  color: C.red },
    { n: "04", title: "構造的上昇地域の深掘り（福岡・北海道…）", time: "15分", color: C.purple },
    { n: "05", title: "まとめ・投資示唆",                        time: "2分",  color: C.green },
  ];

  items.forEach((item, i) => {
    const y = 0.95 + i * 0.85;
    rect(s, 0.4, y, 0.58, 0.58, item.color, item.color, { rounding: 0.04 });
    txt(s, item.n, 0.4, y, 0.58, 0.58,
      { fontSize: 16, bold: true, color: C.white, align: "center", valign: "middle" });
    txt(s, item.title, 1.12, y + 0.1, 7.2, 0.35,
      { fontSize: 16, bold: true, color: C.white });
    txt(s, item.time, 8.7, y + 0.13, 1.1, 0.28,
      { fontSize: 12, color: item.color, align: "right" });
  });
})();

// ════════════════════════════════════════════════════════════════════════
// SLIDE 3: データ概要
// ════════════════════════════════════════════════════════════════════════
(() => {
  const s = pptx.addSlide();
  s.background = { color: C.off };
  bar(s, C.navy);

  txt(s, "01  データ概要・研究目的", 0.35, 0.13, 9.2, 0.45,
    { fontSize: 22, bold: true, color: C.navy });

  const specs = [
    ["データ",   "NII IDR REXデータセット（相続税路線価）"],
    ["形式",     "シェイプファイル（LineString / EPSG:4326）"],
    ["期間",     "2018〜2022年（5年分）"],
    ["路線数",   "約230万路線（全国）"],
    ["構築方法", "2022年・2020年ファイルを serial_id で結合"],
  ];
  specs.forEach(([label, val], i) => {
    const y = 0.75 + i * 0.63;
    txt(s, label, 0.25, y, 1.6, 0.32, { fontSize: 10, bold: true, color: C.navy });
    txt(s, val,   1.9,  y, 3.5, 0.32, { fontSize: 12, color: "222222" });
    if (i < specs.length - 1)
      rect(s, 0.25, y + 0.35, 5.3, 0.01, C.lgray, C.lgray);
  });

  rect(s, 0.25, 3.6, 5.3, 0.68, "FFF8E7", C.gold, { rounding: 0.05, line: { color: C.gold, pt: 1 } });
  txt(s, "研究背景", 0.4, 3.65, 1.2, 0.24, { fontSize: 9, bold: true, color: C.gold });
  txt(s,
    "コロナのようなパンデミックは再び起きうる。「構造的に強い地域」と\nその理由を把握できれば、長期不動産投資の意思決定に直結する。",
    0.4, 3.87, 5.0, 0.35, { fontSize: 10, color: C.navy });

  rect(s, 0.25, 4.36, 5.3, 1.0, C.navy, C.navy, { rounding: 0.05 });
  txt(s, "研究目的", 0.4, 4.42, 5.0, 0.24, { fontSize: 9, bold: true, color: C.gold });
  txt(s,
    "「コロナ」をフィルターとして活用し、\n構造的上昇地域とその要因を空間統計で識別する。\n合わせて構造的下落地域との格差を可視化する。",
    0.4, 4.64, 5.0, 0.65, { fontSize: 11, color: C.white });

  s.addImage({ path: IMG("map_price.png"), x: 5.75, y: 0.62, w: 4.0, h: 4.75 });
  txt(s, "2022年 全国路線価分布", 5.75, 5.3, 4.0, 0.22,
    { fontSize: 9, color: C.gray, align: "center" });
})();

// ════════════════════════════════════════════════════════════════════════
// SLIDE 4: コロナ前後の全国変化
// ════════════════════════════════════════════════════════════════════════
(() => {
  const s = pptx.addSlide();
  s.background = { color: C.off };
  bar(s, C.gold);

  txt(s, "02  コロナ前後の路線価変動", 0.35, 0.13, 9.2, 0.45,
    { fontSize: 22, bold: true, color: C.navy });

  s.addImage({ path: IMG("corona_yearly_change.png"), x: 0.2, y: 0.68, w: 6.1, h: 3.1 });

  const kf = [
    { bg: "FFF0EF", bc: C.red,  text: "2020→2021 のみ\n平均がマイナスに転落" },
    { bg: "FFF9E6", bc: C.gold, text: "下落路線が\n11% → 25% に急増" },
    { bg: "EEF6FF", bc: C.blue, text: "2021→2022 は回復\nただし完全ではない" },
  ];
  kf.forEach((k, i) => {
    const y = 0.72 + i * 1.08;
    rect(s, 6.5, y, 3.2, 0.95, k.bg, k.bc, { rounding: 0.05, line: { color: k.bc, pt: 1.5 } });
    txt(s, k.text, 6.62, y + 0.12, 3.0, 0.72, { fontSize: 13, color: C.navy });
  });

  rect(s, 0.2, 3.92, 9.6, 1.5, "FFF8E7", C.gold, { rounding: 0.05, line: { color: C.gold, pt: 1 } });
  txt(s, "年度別 上昇 / 据え置き / 下落の構成比", 0.4, 3.97, 9.2, 0.3,
    { fontSize: 12, bold: true, color: C.navy });

  const cols = ["2018→19", "2019→20", "2020→21", "2021→22"];
  const ups  = ["35.9%",   "38.2%",   "11.6%",   "30.3%"];
  const flat = ["52.9%",   "52.1%",   "63.4%",   "59.3%"];
  const dns  = ["11.2%",   "9.7%",    "25.0%",   "10.4%"];

  cols.forEach((col, i) => {
    const x = 0.4 + i * 2.35;
    txt(s, col,           x, 4.28, 2.2, 0.25, { fontSize: 10, bold: true, color: C.navy, align: "center" });
    txt(s, "▲ " + ups[i],  x, 4.52, 2.2, 0.22, { fontSize: 11, color: C.red,  align: "center" });
    txt(s, "- " + flat[i], x, 4.73, 2.2, 0.22, { fontSize: 11, color: C.gray, align: "center" });
    txt(s, "▼ " + dns[i],  x, 4.94, 2.2, 0.22, { fontSize: 11, color: C.blue, align: "center" });
  });
})();

// ════════════════════════════════════════════════════════════════════════
// SLIDE 5a-5c: 路線レベル変動マップ（隣接期間 2枚比較 × 3スライド）
// ════════════════════════════════════════════════════════════════════════
[
  {
    title:   "02  コロナ前ベースライン比較",
    context: "2年連続で安定した上昇基調 — コロナ影響はまだ現れていない",
    left:  { label: "① コロナ前  2018→2019", file: "corona_map_road_01.png", color: "C.gold" },
    right: { label: "② コロナ前  2019→2020", file: "corona_map_road_02.png", color: "C.gold" },
  },
  {
    title:   "02  コロナショックの顕在化",
    context: "2020→2021 で都市部・観光地を中心に下落が急増（下落路線 9.7% → 25.0%）",
    left:  { label: "② コロナ前  2019→2020", file: "corona_map_road_02.png", color: "C.gold" },
    right: { label: "③ コロナ禍  2020→2021", file: "corona_map_road_03.png", color: "C.blue" },
  },
  {
    title:   "02  回復期：一時的 vs 構造的",
    context: "多くの地域で回復（赤が戻る）— しかし構造的下落地域では下落が継続",
    left:  { label: "③ コロナ禍  2020→2021", file: "corona_map_road_03.png", color: "C.blue" },
    right: { label: "④ 回復期    2021→2022", file: "corona_map_road_04.png", color: "C.red"  },
  },
].forEach(({ title, context, left, right }) => {
  const s = pptx.addSlide();
  s.background = { color: C.dark };

  txt(s, title, 0.3, 0.05, 9.4, 0.38,
    { fontSize: 18, bold: true, color: C.white });
  txt(s, context, 0.3, 0.43, 9.4, 0.28,
    { fontSize: 11, color: C.gold, italic: true });

  // 左右2枚並置: AR=1.25(10×8)なら w=4.6, h=3.68
  const imgW = 4.6, imgH = 3.68;
  [[left, 0.15], [right, 5.25]].forEach(([side, x]) => {
    const lc = side.color === "C.blue" ? C.blue
             : side.color === "C.red"  ? C.red
             : C.gold;
    txt(s, side.label, x, 0.74, imgW, 0.22,
      { fontSize: 11, bold: true, color: lc });
    s.addImage({ path: IMG(side.file), x, y: 0.96, w: imgW, h: imgH });
  });

  txt(s, "● 赤 = 上昇    ● 灰 = 据え置き    ● 青 = 下落",
    0.3, 5.42, 9.4, 0.18, { fontSize: 9, color: "667788", align: "center" });
});

// ════════════════════════════════════════════════════════════════════════
// SLIDE 6: Donut Effect
// ════════════════════════════════════════════════════════════════════════
(() => {
  const s = pptx.addSlide();
  s.background = { color: C.off };
  bar(s, C.gold);

  txt(s, "02  Donut Effect — 東京都心だけが「真の下落」", 0.35, 0.13, 9.2, 0.45,
    { fontSize: 22, bold: true, color: C.navy });

  s.addImage({ path: IMG("corona_donut_effect.png"), x: 0.15, y: 0.68, w: 6.8, h: 3.2 });

  rect(s, 7.1, 0.72, 2.7, 1.4, "FFE8E8", C.red, { rounding: 0.05, line: { color: C.red, pt: 1.5 } });
  txt(s, "都心 0-5km", 7.2, 0.78, 2.55, 0.3, { fontSize: 12, bold: true, color: "CC0000" });
  txt(s, "コロナ禍に唯一\n実質的な下落\n（中央値 -2.2%）", 7.2, 1.08, 2.55, 0.95, { fontSize: 11, color: "993333" });

  rect(s, 7.1, 2.22, 2.7, 1.4, "E8F4FF", C.blue, { rounding: 0.05, line: { color: C.blue, pt: 1.5 } });
  txt(s, "郊外 5-30km", 7.2, 2.28, 2.55, 0.3, { fontSize: 12, bold: true, color: "0044AA" });
  txt(s, "コロナ前より\nむしろ上昇\n（Donut現象）", 7.2, 2.58, 2.55, 0.95, { fontSize: 11, color: "003388" });

  rect(s, 0.2, 4.05, 9.6, 1.32, "F0F3FF", C.navy, { rounding: 0.05, line: { color: C.navy, pt: 1 } });
  txt(s, "結論", 0.35, 4.1, 1.0, 0.28, { fontSize: 10, bold: true, color: C.gold });
  txt(s,
    "コロナ禍において「都市中心への集積」から「郊外・地方への分散」が起きた（ドーナツ化現象）。\n" +
    "ただし都心の下落は2021→2022で回復 → コロナ型の一時的ショックであることが確認できる。",
    0.35, 4.37, 9.3, 0.9, { fontSize: 12, color: C.navy });
})();

// ════════════════════════════════════════════════════════════════════════
// SLIDE 7: 路線タイプ分類（5タイプ）
// ════════════════════════════════════════════════════════════════════════
(() => {
  const s = pptx.addSlide();
  s.background = { color: C.off };
  bar(s, C.red);

  txt(s, "03  路線を5タイプに分類", 0.35, 0.13, 9.2, 0.45,
    { fontSize: 22, bold: true, color: C.navy });

  // 5カード: 幅1.8, 間隔0.15, 左右余白0.2
  const types = [
    { name: "構造的上昇",   pct: "7.1%",  n: "16万件", color: C.red,    desc: "全期間で上昇\nコロナ禍でも強い\n構造的な勝者" },
    { name: "安定",         pct: "60.5%", n: "140万件", color: C.gray,  desc: "概ね横ばい\nコロナの影響を\nほぼ受けなかった" },
    { name: "回復型",       pct: "6.0%",  n: "14万件", color: C.green,  desc: "禍に下落したが\n2022年に回復\n（一時的ショック）" },
    { name: "コロナ型下落", pct: "12.5%", n: "29万件", color: "E8A838", desc: "コロナ前は安定\n→禍に下落\n2022年も未回復" },
    { name: "構造的下落",   pct: "10.8%", n: "25万件", color: C.blue,   desc: "コロナ前から既に\n下落中\n人口減少・地域衰退" },
  ];

  types.forEach((t, i) => {
    const x = 0.2 + i * 1.95;
    const cw = 1.8;
    rect(s, x, 0.72, cw, 3.95, "FFFFFF", t.color, { rounding: 0.06, line: { color: t.color, pt: 2 } });
    rect(s, x, 0.72, cw, 0.48, t.color, t.color, { rounding: 0.06 });
    txt(s, t.name, x, 0.74, cw, 0.44,
      { fontSize: 11, bold: true, color: C.white, align: "center", valign: "middle" });
    txt(s, t.pct, x, 1.26, cw, 0.65,
      { fontSize: 30, bold: true, color: t.color, align: "center" });
    txt(s, t.n,   x, 1.89, cw, 0.26,
      { fontSize: 10, color: C.gray, align: "center" });
    rect(s, x + 0.12, 2.2, cw - 0.24, 0.02, C.lgray, C.lgray);
    txt(s, t.desc, x + 0.1, 2.28, cw - 0.18, 2.2,
      { fontSize: 10, color: "333333" });
  });

  rect(s, 0.2, 4.82, 9.6, 0.65, C.navy, C.navy, { rounding: 0.05 });
  txt(s,
    "※ 全国 230万路線を分類（2018–2022年パネル）｜ コロナ下落計 23.3%（コロナ型12.5% + 構造的10.8%）のうち回復型は約3割",
    0.35, 4.87, 9.3, 0.55, { fontSize: 11, color: C.white });
})();

// ════════════════════════════════════════════════════════════════════════
// SLIDE 8: SHAP — コロナショック耐性の条件
// ════════════════════════════════════════════════════════════════════════
(() => {
  const s = pptx.addSlide();
  s.background = { color: C.off };
  bar(s, C.red);

  txt(s, "03  コロナショック耐性の条件 — LightGBM + SHAP", 0.35, 0.1, 9.2, 0.42,
    { fontSize: 20, bold: true, color: C.navy });
  txt(s, "「コロナ禍の変化率」を目的変数にした機械学習で、耐性を高める特徴を定量化",
    0.35, 0.52, 9.2, 0.26, { fontSize: 11, color: C.gray, italic: true });

  // SHAP Beeswarm 画像（figsize=10×7, AR=1.43）
  s.addImage({ path: IMG("shap_covid_shock.png"), x: 0.12, y: 0.82, w: 5.7, h: 3.99 });

  // 右パネル: 主要知見
  rect(s, 6.05, 0.82, 3.75, 0.5, C.navy, C.navy, { rounding: 0.04 });
  txt(s, "空間CV  R² = 0.18　RMSE = 1.87pp",
    6.15, 0.88, 3.55, 0.36, { fontSize: 10, color: C.gold });

  const findings = [
    { icon: "▼", color: C.blue,  text: "高価格路線・商業地\nコロナに最も脆弱" },
    { icon: "▲", color: C.red,   text: "東京から遠い\n地方ほど耐性あり（Donut効果）" },
    { icon: "▲", color: C.red,   text: "コロナ前の上昇基調\n「勢い」がある路線は耐性高い" },
    { icon: "▲", color: C.red,   text: "福岡・西日本圏\n経度が示す地域耐性の差" },
  ];

  findings.forEach((f, i) => {
    const y = 1.46 + i * 1.02;
    rect(s, 6.05, y, 3.75, 0.88,
      f.icon === "▲" ? "FFF0EF" : "EEF4FF",
      f.color, { rounding: 0.04, line: { color: f.color, pt: 1.2 } });
    txt(s, f.icon, 6.12, y + 0.1, 0.28, 0.32,
      { fontSize: 14, bold: true, color: f.color });
    txt(s, f.text, 6.42, y + 0.08, 3.28, 0.72,
      { fontSize: 11, color: C.navy });
  });
})();

// ════════════════════════════════════════════════════════════════════════
// SLIDE 9: コロナ型 vs 構造的下落マップ
// ════════════════════════════════════════════════════════════════════════
(() => {
  const s = pptx.addSlide();
  s.background = { color: C.off };
  bar(s, C.red);

  txt(s, "03  下落の「原因」の地域差", 0.35, 0.13, 9.2, 0.45,
    { fontSize: 22, bold: true, color: C.navy });
  txt(s, "赤 = コロナ起因の下落が多い地域　　青 = コロナ前からの構造的下落が多い地域",
    0.35, 0.6, 9.2, 0.3, { fontSize: 12, color: C.navy });

  s.addImage({ path: IMG("corona_road_type_map.png"), x: 1.2, y: 0.92, w: 7.6, h: 4.4 });
})();

// ════════════════════════════════════════════════════════════════════════
// SLIDE 9: ずっと上昇・ずっと下落マップ
// ════════════════════════════════════════════════════════════════════════
(() => {
  const s = pptx.addSlide();
  s.background = { color: C.dark };

  txt(s, "「コロナフィルター」が浮き彫りにした地域", 0.3, 0.1, 9.4, 0.45,
    { fontSize: 20, bold: true, color: C.white });
  txt(s, "全4期間（2018〜2022）を通じてずっと上昇 / ずっと下落だった路線", 0.3, 0.52, 9.4, 0.28,
    { fontSize: 12, color: C.gold });

  s.addImage({ path: IMG("corona_always_trend.png"), x: 0.2, y: 0.85, w: 5.6, h: 4.65 });

  txt(s, "▲ 構造的上昇（投資注目）", 5.95, 0.88, 3.9, 0.3, { fontSize: 12, bold: true, color: C.red });
  const upList = [
    ["福岡（44.3%）",   "アジア玄関口・人口増加継続\n→ 博多駅周辺・天神の地価が全国上位"],
    ["宮城（40.8%）",   "震災復興需要の持続\n→ 仙台都心の再開発・人口集積"],
    ["北海道（35.2%）", "ニセコ外資・札幌再開発\n→ インバウンド復活で再加速中"],
    ["沖縄（28.5%）",   "観光需要の継続的上昇\n→ 那覇市街の商業地が堅調"],
  ];
  upList.forEach(([name, reason], i) => {
    const y = 1.2 + i * 0.92;
    rect(s, 5.9, y, 3.9, 0.82, "1A0808", C.red, { rounding: 0.04, line: { color: C.red, pt: 0.8 } });
    txt(s, name,   6.0, y + 0.04, 3.75, 0.24, { fontSize: 11, bold: true, color: C.red });
    txt(s, reason, 6.0, y + 0.3,  3.75, 0.44, { fontSize: 9,  color: "CCDDEE" });
  });

  txt(s, "▼ 構造的下落", 5.95, 4.92, 3.9, 0.28, { fontSize: 11, bold: true, color: C.blue });
  txt(s, "神奈川郊外 / 静岡 / 四国 ─ 人口流出・産業空洞化",
    5.95, 5.2, 3.9, 0.28, { fontSize: 9, color: "AABBCC" });
})();

// ════════════════════════════════════════════════════════════════════════
// SLIDE 10: 各地域の深掘り（プレースホルダー）
// ════════════════════════════════════════════════════════════════════════
(() => {
  const s = pptx.addSlide();
  s.background = { color: C.off };
  bar(s, C.purple);

  txt(s, "04  各地域の深掘り分析", 0.35, 0.13, 9.2, 0.45,
    { fontSize: 22, bold: true, color: C.navy });

  const areas = [
    { name: "福岡・沖縄",                color: C.red,    member: "担当: A（主力）",
      hint: "人口増加 / アジア玄関口\nインバウンド需要の空間分布\n→ 投資先として最注目" },
    { name: "北海道・宮城",              color: "E8534A", member: "担当: A（副）",
      hint: "ニセコ外資 / 震災復興\n札幌・仙台の都市再開発\n→ 上昇エリアの内部格差" },
    { name: "構造的下落地域\n（太平洋沿い・郊外）", color: C.blue, member: "担当: B・C",
      hint: "四国・静岡・神奈川郊外\n人口流出・南海トラフリスク\n→ 上昇地域との比較対象" },
  ];

  areas.forEach((a, i) => {
    const x = 0.22 + i * 3.26;
    rect(s, x, 0.72, 3.1, 4.75, "FFFFFF", a.color, { rounding: 0.06, line: { color: a.color, pt: 2 } });
    rect(s, x, 0.72, 3.1, 0.52, a.color, a.color, { rounding: 0.06 });
    txt(s, a.name, x, 0.75, 3.1, 0.48,
      { fontSize: 13, bold: true, color: C.white, align: "center", valign: "middle" });
    txt(s, a.member, x, 1.28, 3.1, 0.28,
      { fontSize: 11, color: a.color, align: "center" });
    rect(s, x + 0.2, 1.62, 2.7, 0.02, C.lgray, C.lgray);
    txt(s, "分析の視点:", x + 0.18, 1.7, 2.75, 0.25,
      { fontSize: 10, bold: true, color: C.gray });
    txt(s, a.hint, x + 0.18, 1.95, 2.75, 0.8,
      { fontSize: 11, color: "333333" });
    rect(s, x + 0.18, 2.82, 2.75, 2.4, "F7F8FA", C.lgray,
      { rounding: 0.05, line: { color: C.lgray, pt: 1, dashType: "dash" } });
    txt(s, "（各自の分析グラフ・地図をここに）",
      x + 0.18, 3.85, 2.75, 0.45, { fontSize: 9, color: C.gray, align: "center" });
  });
})();

// ════════════════════════════════════════════════════════════════════════
// SLIDE 11: 結論
// ════════════════════════════════════════════════════════════════════════
(() => {
  const s = pptx.addSlide();
  s.background = { color: C.dark };
  s.addImage({ path: IMG("corona_always_trend.png"), x: 0, y: 0, w: 10, h: 5.625, transparency: 82 });

  txt(s, "05  結論", 0.4, 0.15, 3.0, 0.38, { fontSize: 13, color: C.gold });
  txt(s, "コロナは「フィルター」として機能した", 0.4, 0.5, 9.2, 0.65,
    { fontSize: 27, bold: true, color: C.white });
  rect(s, 0.4, 1.18, 9.2, 0.04, C.blue, C.blue);

  const pts = [
    ["コロナは「フィルター」だった — 構造的に強い地域だけが残った"],
    ["構造的勝者: 福岡・北海道・宮城・沖縄（人口増・インバウンド・復興）"],
    ["コロナ型下落（18.5%）は一時的ショック — 2022年に多くが回復"],
    ["構造的敗者: 神奈川郊外・四国・山陰（人口流出・産業空洞化）"],
  ];

  pts.forEach(([text], i) => {
    const y = 1.32 + i * 0.82;
    rect(s, 0.35, y, 9.3, 0.68, "FFFFFF", "FFFFFF",
      { rounding: 0.04, transparency: 88, line: { color: "FFFFFF", pt: 0.5, transparency: 75 } });
    txt(s, text, 0.5, y + 0.1, 9.1, 0.48, { fontSize: 13, color: C.white });
  });

  rect(s, 0.35, 4.72, 9.3, 0.75, C.red, C.red, { rounding: 0.04 });
  txt(s, "投資示唆",
    0.5, 4.76, 1.5, 0.28, { fontSize: 10, bold: true, color: "FFE0DD" });
  txt(s,
    "次のパンデミックでも「構造的上昇」地域は強い ─ 福岡・北海道の都市部が長期投資先の筆頭候補",
    0.5, 5.02, 9.1, 0.38, { fontSize: 12, bold: true, color: C.white });
})();

// ── 出力 ──────────────────────────────────────────────────────────────
pptx.writeFile({ fileName: "/Users/KASU/data_analysis/outputs/PBL発表_v2.pptx" })
  .then(() => console.log("Done: /Users/KASU/data_analysis/outputs/PBL発表_v2.pptx"))
  .catch((e) => { console.error("Error:", e); process.exit(1); });
