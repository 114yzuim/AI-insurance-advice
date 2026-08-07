const pptxgen = require("pptxgenjs");
const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.title = "基於RAG之AI保險顧問系統設計與評估";

const C = {
  darkBg:"0A3D5C", midBg:"1C7293", accent:"00B4D8",
  accentGreen:"02C39A", lightBg:"F0F7FA", cardBg:"FFFFFF",
  textDark:"1E293B", textMid:"475569", textLight:"FFFFFF",
  border:"D1E8F0", grey:"64748B", amber:"D97706", red:"B03A2E", purple:"6D4C9C"
};
const makeShadow = () => ({type:"outer",color:"000000",blur:8,offset:3,angle:135,opacity:0.12});

function addHeader(slide, title, subtitle, pageNum) {
  slide.addShape(pres.shapes.RECTANGLE,{x:0,y:0,w:10,h:1.0,fill:{color:C.darkBg},line:{color:C.darkBg}});
  slide.addShape(pres.shapes.RECTANGLE,{x:0,y:0,w:0.14,h:1.0,fill:{color:C.accent},line:{color:C.accent}});
  slide.addText(title,{x:0.32,y:0.07,w:8.7,h:0.52,fontSize:20,bold:true,color:C.textLight,fontFace:"Calibri",margin:0,valign:"middle"});
  if(subtitle) slide.addText(subtitle,{x:0.32,y:0.57,w:8.7,h:0.36,fontSize:11.5,color:"A8DAEC",fontFace:"Calibri",margin:0,valign:"middle"});
  if(pageNum) slide.addText(pageNum,{x:9.35,y:0.07,w:0.55,h:0.86,fontSize:11,color:"6B9EB5",align:"right",valign:"middle",fontFace:"Calibri",margin:0});
}
function addFooter(slide,label){
  slide.addShape(pres.shapes.RECTANGLE,{x:0,y:5.52,w:10,h:0.105,fill:{color:C.border},line:{color:C.border}});
  slide.addText(label||"基於RAG之AI保險顧問系統｜2026",{x:0.32,y:5.46,w:9.36,h:0.16,fontSize:8,color:C.grey,fontFace:"Calibri",margin:0});
}

/* ══════════ S1 Title ══════════ */
{
  const s = pres.addSlide();
  s.background = {color:C.darkBg};
  s.addShape(pres.shapes.RECTANGLE,{x:0,y:0,w:0.28,h:5.625,fill:{color:C.accent},line:{color:C.accent}});
  s.addShape(pres.shapes.RECTANGLE,{x:7.6,y:0,w:2.4,h:5.625,fill:{color:"0D4A6A"},line:{color:"0D4A6A"}});
  s.addText("基於檢索增強生成之",{x:0.65,y:0.95,w:6.8,h:0.65,fontSize:25,bold:true,color:C.textLight,fontFace:"Calibri"});
  s.addText("AI 保險顧問系統",{x:0.65,y:1.58,w:6.8,h:0.72,fontSize:31,bold:true,color:C.accent,fontFace:"Calibri"});
  s.addText("設計與評估：以台灣市場為例",{x:0.65,y:2.3,w:6.8,h:0.55,fontSize:19,color:"A8DAEC",fontFace:"Calibri"});
  ["RAG","LLM-as-Judge","AHP","信度分析","台灣保險市場"].forEach((t,i)=>{
    s.addShape(pres.shapes.RECTANGLE,{x:0.65+i*1.36,y:3.1,w:1.24,h:0.36,fill:{color:C.midBg},line:{color:C.accent,pt:1}});
    s.addText(t,{x:0.65+i*1.36,y:3.1,w:1.24,h:0.36,fontSize:9.5,color:C.textLight,align:"center",valign:"middle",fontFace:"Calibri",margin:0});
  });
  s.addText("完整版研討會報告 — 含評審意見回應與方法論修正記錄",{x:0.65,y:3.7,w:6.6,h:0.4,fontSize:12,italic:true,color:"6B9EB5",fontFace:"Calibri"});
  s.addShape(pres.shapes.RECTANGLE,{x:0,y:5.1,w:10,h:0.525,fill:{color:"061E2E"},line:{color:"061E2E"}});
  s.addText("研討會報告　|　2026",{x:0.65,y:5.1,w:9,h:0.525,fontSize:13,color:"6B9EB5",valign:"middle",fontFace:"Calibri",margin:0});
}

/* ══════════ S2 背景與動機 ══════════ */
{
  const s = pres.addSlide();
  s.background = {color:C.lightBg};
  addHeader(s,"研究背景與動機","台灣保險市場的結構性問題","02");
  [{title:"資訊不對稱",body:"業務員受佣金驅動，推薦難以中立；消費者缺乏獨立資訊來源（Chen et al., 2022; Chiappori et al., 2006）",color:C.darkBg},
   {title:"現有工具不足",body:"第三方比價平台僅提供關鍵字篩選，無法理解自然語言需求，不提供情境化建議",color:C.midBg},
   {title:"LLM 幻覺風險",body:"純記憶型 LLM 可能生成與保單條款不符的資訊，在高度規範的保險領域尤具危害性",color:"1A5276"}
  ].forEach((card,i)=>{
    const x=0.42+i*3.1;
    s.addShape(pres.shapes.RECTANGLE,{x,y:1.16,w:2.9,h:3.1,fill:{color:C.cardBg},line:{color:C.border,pt:1},shadow:makeShadow()});
    s.addShape(pres.shapes.RECTANGLE,{x,y:1.16,w:2.9,h:0.54,fill:{color:card.color},line:{color:card.color}});
    s.addText(card.title,{x:x+0.15,y:1.16,w:2.6,h:0.54,fontSize:13,bold:true,color:C.textLight,fontFace:"Calibri",margin:0,valign:"middle"});
    s.addText(card.body,{x:x+0.15,y:1.82,w:2.6,h:2.3,fontSize:11.5,color:C.textDark,fontFace:"Calibri",valign:"top"});
  });
  s.addShape(pres.shapes.RECTANGLE,{x:0.42,y:4.42,w:9.16,h:0.62,fill:{color:C.accent,transparency:88},line:{color:C.accent,pt:2}});
  s.addText("研究問題：RAG 架構的 AI 保險顧問系統，能否在台灣市場實現技術可行的消費者導向顧問服務？",{x:0.6,y:4.42,w:9.0,h:0.62,fontSize:12.5,bold:true,color:C.darkBg,fontFace:"Calibri",valign:"middle",margin:0});
  addFooter(s);
}

/* ══════════ S3 系統架構 ══════════ */
{
  const s = pres.addSlide();
  s.background = {color:C.lightBg};
  addHeader(s,"系統架構","三層架構 × RAG Pipeline","03");
  [{label:"前端：Next.js + TypeScript + Tailwind CSS",color:C.accent},
   {label:"後端：FastAPI（Python）RESTful API",color:C.midBg},
   {label:"RAG Pipeline：BGE-M3 + BM25 + RRF 混合檢索",color:"1A5276"},
   {label:"PDF 條款解析：Docling（Document Intelligence）",color:C.darkBg},
   {label:"生成核心：Claude API（claude-sonnet-4-6）",color:"082030"}
  ].forEach((layer,i)=>{
    s.addShape(pres.shapes.RECTANGLE,{x:0.42,y:1.1+i*0.78,w:5.2,h:0.64,fill:{color:layer.color},line:{color:layer.color}});
    s.addText(layer.label,{x:0.58,y:1.1+i*0.78,w:5.0,h:0.64,fontSize:11.5,color:C.textLight,valign:"middle",fontFace:"Calibri",margin:0});
    if(i<4) s.addShape(pres.shapes.RECTANGLE,{x:2.9,y:1.74+i*0.78,w:0.04,h:0.14,fill:{color:"94A3B8"},line:{color:"94A3B8"}});
  });
  s.addShape(pres.shapes.RECTANGLE,{x:6.0,y:1.08,w:3.6,h:4.0,fill:{color:C.cardBg},line:{color:C.border},shadow:makeShadow()});
  s.addText("核心規格",{x:6.2,y:1.16,w:3.2,h:0.4,fontSize:14,bold:true,color:C.darkBg,fontFace:"Calibri",margin:0});
  [["780","筆保險商品"],["5","家保險公司"],["12","份 PDF 條款"],["834","個條款 chunks"],["top-5/6","語意檢索結果"]].forEach(([n,l],i)=>{
    s.addText(n,{x:6.2,y:1.65+i*0.65,w:1.5,h:0.5,fontSize:22,bold:true,color:C.accent,fontFace:"Calibri",margin:0});
    s.addText(l,{x:7.7,y:1.73+i*0.65,w:1.7,h:0.36,fontSize:11.5,color:C.textMid,fontFace:"Calibri",margin:0,valign:"middle"});
  });
  addFooter(s);
}

/* ══════════ S4 四技術策略 ══════════ */
{
  const s = pres.addSlide();
  s.background = {color:C.lightBg};
  addHeader(s,"四種檢索-生成技術策略","知識供給遞增光譜：從無檢索到條款級 grounding","04");
  [{code:"no_rag",label:"純 LLM",color:C.grey,pro:"零檢索成本",con:"幻覺風險最高、不可溯源",use:"一般保險知識問答"},
   {code:"sbert_only",label:"純向量檢索",color:"1976D2",pro:"輕量、確定性",con:"無推理、無揭露",use:"商品搜尋／比價"},
   {code:"metadata_rag",label:"商品 metadata RAG",color:C.midBg,pro:"可指名商品、成本低",con:"無條款細節",use:"商品多、首階段推薦"},
   {code:"pdf_rag",label:"Full PDF RAG（核心）",color:C.accentGreen,pro:"可引用條款、幻覺最低",con:"需解析 PDF、成本高",use:"高度規範領域"}
  ].forEach((c,i)=>{
    const x=0.36+i*2.36;
    s.addShape(pres.shapes.RECTANGLE,{x,y:1.1,w:2.2,h:3.85,fill:{color:C.cardBg},line:{color:C.border,pt:1},shadow:makeShadow()});
    s.addShape(pres.shapes.RECTANGLE,{x,y:1.1,w:2.2,h:0.7,fill:{color:c.color},line:{color:c.color}});
    s.addText(c.code,{x:x+0.1,y:1.12,w:2.0,h:0.36,fontSize:12,bold:true,color:"FFFFFF",fontFace:"Consolas",margin:0,valign:"middle"});
    s.addText(c.label,{x:x+0.1,y:1.45,w:2.0,h:0.32,fontSize:10.5,color:"EAF6FF",fontFace:"Calibri",margin:0,valign:"middle"});
    s.addText([{text:"優點\n",options:{bold:true,color:C.accentGreen,fontSize:10}},{text:c.pro,options:{color:C.textDark,fontSize:11}}],{x:x+0.12,y:1.92,w:1.96,h:0.8,fontFace:"Calibri",valign:"top",margin:0});
    s.addText([{text:"限制\n",options:{bold:true,color:C.red,fontSize:10}},{text:c.con,options:{color:C.textDark,fontSize:11}}],{x:x+0.12,y:2.72,w:1.96,h:0.9,fontFace:"Calibri",valign:"top",margin:0});
    s.addText([{text:"適用\n",options:{bold:true,color:C.midBg,fontSize:10}},{text:c.use,options:{color:C.textDark,fontSize:11}}],{x:x+0.12,y:3.65,w:1.96,h:1.05,fontFace:"Calibri",valign:"top",margin:0});
  });
  s.addText("貢獻不在單項技術，而在「整合進台灣保險顧問應用 + 統一框架系統性比較成本效益權衡」",{x:0.36,y:4.92,w:9.28,h:0.28,fontSize:10.5,bold:true,color:C.darkBg,align:"center",italic:true,fontFace:"Calibri"});
  addFooter(s);
}

/* ══════════ S5 與市場做法對位 ══════════ */
{
  const s = pres.addSlide();
  s.background = {color:C.lightBg};
  addHeader(s,"與市面現有做法之對位","本研究把分散於市場的技術路線，整合進同一套應用比較","05");
  const rows = [
    ["no_rag","通用聊天機器人（直接問 ChatGPT）","幻覺未受控，非保險專用",C.grey],
    ["sbert_only","第三方比價平台關鍵字／向量搜尋","提供清單，不做需求推理與條款解讀",C.midBg],
    ["metadata_rag","多數商用 RAG 客服（僅索引商品摘要）","成本低，條款精確度受限",C.darkBg],
    ["pdf_rag","Document Intelligence + RAG 前沿（Azure DI、LlamaParse）","本研究於台灣保險場景提供實證",C.accentGreen],
  ];
  s.addShape(pres.shapes.RECTANGLE,{x:0.42,y:1.16,w:1.9,h:0.48,fill:{color:C.darkBg},line:{color:"FFFFFF",pt:1}});
  s.addText("技術策略",{x:0.42,y:1.16,w:1.9,h:0.48,fontSize:11.5,bold:true,color:"FFFFFF",align:"center",valign:"middle",fontFace:"Calibri",margin:0});
  s.addShape(pres.shapes.RECTANGLE,{x:2.32,y:1.16,w:3.8,h:0.48,fill:{color:C.darkBg},line:{color:"FFFFFF",pt:1}});
  s.addText("市場類比",{x:2.32,y:1.16,w:3.8,h:0.48,fontSize:11.5,bold:true,color:"FFFFFF",align:"center",valign:"middle",fontFace:"Calibri",margin:0});
  s.addShape(pres.shapes.RECTANGLE,{x:6.12,y:1.16,w:3.46,h:0.48,fill:{color:C.darkBg},line:{color:"FFFFFF",pt:1}});
  s.addText("市場現況與本研究定位",{x:6.12,y:1.16,w:3.46,h:0.48,fontSize:11.5,bold:true,color:"FFFFFF",align:"center",valign:"middle",fontFace:"Calibri",margin:0});
  rows.forEach((r,i)=>{
    const y=1.64+i*0.8;
    s.addShape(pres.shapes.RECTANGLE,{x:0.42,y,w:1.9,h:0.8,fill:{color:C.cardBg},line:{color:C.border,pt:1}});
    s.addShape(pres.shapes.RECTANGLE,{x:0.42,y,w:0.1,h:0.8,fill:{color:r[3]},line:{color:r[3]}});
    s.addText(r[0],{x:0.56,y,w:1.7,h:0.8,fontSize:10.5,bold:true,color:r[3],fontFace:"Consolas",valign:"middle",margin:0});
    s.addShape(pres.shapes.RECTANGLE,{x:2.32,y,w:3.8,h:0.8,fill:{color:C.cardBg},line:{color:C.border,pt:1}});
    s.addText(r[1],{x:2.44,y,w:3.6,h:0.8,fontSize:10.5,color:C.textDark,valign:"middle",fontFace:"Calibri",margin:0});
    s.addShape(pres.shapes.RECTANGLE,{x:6.12,y,w:3.46,h:0.8,fill:{color:C.cardBg},line:{color:C.border,pt:1}});
    s.addText(r[2],{x:6.24,y,w:3.26,h:0.8,fontSize:10.5,color:C.textDark,valign:"middle",fontFace:"Calibri",margin:0});
  });
  s.addText("受規範保險 QA 穩健性研究（Beauchemin & Khoury, 2024）：RAG 可能因格式／安全衝突退化，與 §4.4「切割+profile」表現不佳相呼應",
    {x:0.42,y:4.86,w:9.16,h:0.28,fontSize:9.5,italic:true,color:C.textMid,align:"center",fontFace:"Calibri"});
  addFooter(s);
}

/* ══════════ S6 評估方法：LLM-as-Judge + AHP ══════════ */
{
  const s = pres.addSlide();
  s.background = {color:C.lightBg};
  addHeader(s,"評估方法","跨模型 LLM-as-Judge × AHP 法規錨定加權","06");
  s.addShape(pres.shapes.RECTANGLE,{x:0.42,y:1.1,w:4.5,h:4.0,fill:{color:C.cardBg},line:{color:C.border},shadow:makeShadow()});
  s.addShape(pres.shapes.RECTANGLE,{x:0.42,y:1.1,w:4.5,h:0.5,fill:{color:C.darkBg},line:{color:C.darkBg}});
  s.addText("跨模型 LLM-as-Judge",{x:0.58,y:1.1,w:4.2,h:0.5,fontSize:13.5,bold:true,color:C.textLight,fontFace:"Calibri",margin:0,valign:"middle"});
  [["Claude（sonnet-4-6）","生成端 + 評審端"],["GPT-4o（OpenAI）","評審端"],["Gemini 2.5 Flash","評審端"]].forEach((j,i)=>{
    s.addShape(pres.shapes.OVAL,{x:0.62,y:1.78+i*0.74,w:0.36,h:0.36,fill:{color:C.accent},line:{color:C.accent}});
    s.addText((i+1).toString(),{x:0.62,y:1.78+i*0.74,w:0.36,h:0.36,fontSize:12,bold:true,color:"FFFFFF",align:"center",valign:"middle",fontFace:"Calibri",margin:0});
    s.addText(j[0],{x:1.1,y:1.78+i*0.74,w:3.7,h:0.28,fontSize:12,bold:true,color:C.textDark,fontFace:"Calibri",margin:0});
    s.addText(j[1],{x:1.1,y:2.03+i*0.74,w:3.7,h:0.22,fontSize:10,color:C.textMid,italic:true,fontFace:"Calibri",margin:0});
  });
  s.addShape(pres.shapes.RECTANGLE,{x:0.58,y:4.22,w:4.18,h:0.78,fill:{color:C.accentGreen,transparency:85},line:{color:C.accentGreen,pt:1}});
  s.addText("36 筆回應 × 3 評審 = 108 次評估\n（3 情境 × 4 策略 × 3 次重複生成）",{x:0.68,y:4.22,w:4.0,h:0.78,fontSize:10.5,bold:true,color:"005C47",fontFace:"Calibri",valign:"middle",margin:0});
  s.addShape(pres.shapes.RECTANGLE,{x:5.1,y:1.1,w:4.5,h:4.0,fill:{color:C.cardBg},line:{color:C.border},shadow:makeShadow()});
  s.addShape(pres.shapes.RECTANGLE,{x:5.1,y:1.1,w:4.5,h:0.5,fill:{color:C.midBg},line:{color:C.midBg}});
  s.addText("AHP 維度加權（法規錨定順序）",{x:5.26,y:1.1,w:4.2,h:0.5,fontSize:13.5,bold:true,color:C.textLight,fontFace:"Calibri",margin:0,valign:"middle"});
  [{code:"D1",name:"需求覆蓋率",w:"0.648",anchor:"金保法 §9 適合度原則",color:C.darkBg},
   {code:"D2",name:"條款一致性",w:"0.230",anchor:"業務員管理規則 §19 禁不實說明",color:C.midBg},
   {code:"D3",name:"資訊完整性",w:"0.122",anchor:"金保法 §10 說明義務",color:C.accent}
  ].forEach((d,i)=>{
    const y=1.78+i*1.0;
    s.addText(d.code+"  "+d.name,{x:5.26,y,w:2.7,h:0.32,fontSize:12.5,bold:true,color:C.textDark,fontFace:"Calibri",margin:0});
    s.addText(d.w,{x:8.2,y,w:1.2,h:0.32,fontSize:16,bold:true,color:d.color,align:"right",fontFace:"Calibri",margin:0});
    s.addShape(pres.shapes.RECTANGLE,{x:5.26,y:y+0.37,w:3.7,h:0.15,fill:{color:"E2EBF0"},line:{color:"E2EBF0"}});
    s.addShape(pres.shapes.RECTANGLE,{x:5.26,y:y+0.37,w:3.7*parseFloat(d.w),h:0.15,fill:{color:d.color},line:{color:d.color}});
    s.addText("錨定："+d.anchor,{x:5.26,y:y+0.55,w:4.2,h:0.24,fontSize:9,color:C.textMid,italic:true,fontFace:"Calibri",margin:0});
  });
  addFooter(s);
}

/* ══════════ S7 AHP 誠實界定 + 敏感度分析 ══════════ */
{
  const s = pres.addSlide();
  s.background = {color:C.lightBg};
  addHeader(s,"AHP 權重的誠實界定與敏感度分析","回應「比例怎麼來、CR 代表正確嗎、換人會不會不同」","07");
  s.addShape(pres.shapes.RECTANGLE,{x:0.42,y:1.1,w:9.16,h:1.05,fill:{color:C.amber,transparency:90},line:{color:C.amber,pt:1.5}});
  s.addText([
    {text:"順序有法源、數值是判斷：",options:{bold:true,color:"92400E",fontSize:12}},
    {text:"D1≻D2≻D3 的順序錨定於法規；成對比較數值（3/5/2）為 Saaty 尺度上的研究者判斷。",options:{color:C.textDark,fontSize:11.5,breakLine:true}},
    {text:"CR = 0.003 只證明判斷不自相矛盾，不證明數值「客觀正確」；換評判者或產業，權重會不同。",options:{color:C.textDark,fontSize:11.5}}
  ],{x:0.6,y:1.1,w:8.8,h:1.05,fontFace:"Calibri",valign:"middle",margin:0});
  s.addText("權重敏感度分析：pdf_rag 在四種權重方案下均維持領先",{x:0.42,y:2.32,w:9.16,h:0.32,fontSize:12.5,bold:true,color:C.darkBg,fontFace:"Calibri"});
  const head = ["權重方案","D1:D2:D3","領先策略","pdf_rag W"];
  const data = [
    ["等權","0.33:0.33:0.33","pdf_rag","2.803"],
    ["本研究 AHP","0.648:0.230:0.122","pdf_rag","2.892"],
    ["D2 強調（法遵視角）","0.230:0.648:0.122","pdf_rag","2.754"],
    ["D3 強調（風險揭露）","0.122:0.230:0.648","pdf_rag","2.756"],
  ];
  const cw=[3.0,2.5,2.0,1.66], x0=0.42, y0=2.7;
  let cx=x0;
  head.forEach((h,j)=>{
    s.addShape(pres.shapes.RECTANGLE,{x:cx,y:y0,w:cw[j],h:0.42,fill:{color:C.darkBg},line:{color:"FFFFFF",pt:1}});
    s.addText(h,{x:cx,y:y0,w:cw[j],h:0.42,fontSize:11,bold:true,color:"FFFFFF",align:"center",valign:"middle",fontFace:"Calibri",margin:0});
    cx+=cw[j];
  });
  data.forEach((row,i)=>{
    cx=x0; const y=y0+0.42+i*0.42;
    row.forEach((cell,j)=>{
      const isWin = j===2;
      s.addShape(pres.shapes.RECTANGLE,{x:cx,y,w:cw[j],h:0.42,fill:{color:isWin?"E3F7F1":C.cardBg},line:{color:C.border,pt:1}});
      s.addText(cell,{x:cx,y,w:cw[j],h:0.42,fontSize:10.5,bold:(j===2||j===3),color:isWin?"005C47":C.textDark,align:"center",valign:"middle",fontFace:"Calibri",margin:0});
      cx+=cw[j];
    });
  });
  s.addText("→ 核心結論「pdf_rag 領先」不依賴特定權重，緩解「結論由權重人為導出」之疑慮",{x:0.42,y:4.84,w:9.16,h:0.3,fontSize:10.5,bold:true,color:C.accentGreen,align:"center",italic:true,fontFace:"Calibri"});
  addFooter(s);
}

/* ══════════ S8 評審信度統計（NEW） ══════════ */
{
  const s = pres.addSlide();
  s.background = {color:C.lightBg};
  addHeader(s,"評審信度統計","Pearson r 之外：補充次序量表更適切的信度指標","08");
  s.addText("Pearson r 衡量兩兩線性相關，但 D1/D2/D3 為次序評分（1–3 分），補充 Kendall's W 與 Krippendorff's α 更為適切",
    {x:0.42,y:1.06,w:9.16,h:0.3,fontSize:11,italic:true,color:C.textMid,fontFace:"Calibri"});
  const head=["評分標的","Kendall's W","Krippendorff's α","一致性判讀"];
  const data=[
    ["W-Score（加權總分）","0.837","0.909","良好"],
    ["D1 需求覆蓋率","0.716","0.897","良好"],
    ["D2 條款一致性","0.685","0.784","可接受"],
    ["D3 資訊完整性","0.631","0.735","可接受"],
  ];
  const cw=[3.3,2.0,2.3,1.56], x0=0.42, y0=1.42, rowH=0.38;
  let cx=x0;
  head.forEach((h,j)=>{
    s.addShape(pres.shapes.RECTANGLE,{x:cx,y:y0,w:cw[j],h:rowH,fill:{color:C.darkBg},line:{color:"FFFFFF",pt:1}});
    s.addText(h,{x:cx,y:y0,w:cw[j],h:rowH,fontSize:10.5,bold:true,color:"FFFFFF",align:"center",valign:"middle",fontFace:"Calibri",margin:0});
    cx+=cw[j];
  });
  data.forEach((row,i)=>{
    cx=x0; const y=y0+rowH+i*rowH; const good=row[3]==="良好";
    row.forEach((cell,j)=>{
      s.addShape(pres.shapes.RECTANGLE,{x:cx,y,w:cw[j],h:rowH,fill:{color:j===3?(good?"E3F7F1":"FFF4D6"):C.cardBg},line:{color:C.border,pt:1}});
      s.addText(cell,{x:cx,y,w:cw[j],h:rowH,fontSize:10,bold:j===0||j===3,color:j===3?(good?"005C47":"92400E"):C.textDark,align:j===0?"left":"center",valign:"middle",fontFace:"Calibri",margin:j===0?{left:0.1}:0});
      cx+=cw[j];
    });
  });
  const tableBottom = y0 + rowH + data.length*rowH; // 1.42 + 0.38*5 = 3.32
  const calloutY = tableBottom + 0.14; // 3.46
  s.addShape(pres.shapes.RECTANGLE,{x:0.42,y:calloutY,w:9.16,h:1.08,fill:{color:C.cardBg},line:{color:C.accent,pt:1.5},shadow:makeShadow()});
  s.addText([
    {text:"誠實分層結果：",options:{bold:true,color:C.darkBg,fontSize:12,breakLine:true}},
    {text:"D1 與整體 W-Score 一致性高（α≥0.89）；D2/D3 較低（α=0.73–0.78，可接受但非良好），反映評審對「條款一致性」「資訊完整性」等需細緻文本判讀的維度，主觀性較高。此分層結果未被隱藏，並提示後續引入人類專家評審校準之必要性。",options:{color:C.textDark,fontSize:10.5}}
  ],{x:0.58,y:calloutY+0.05,w:8.84,h:0.98,fontFace:"Calibri",valign:"middle",margin:0});
  s.addText("rubric 修正前後評審一致性：run 層級 Pearson r 維持於 0.92–0.97（三組配對中一組微升、兩組微降，變動 ±0.03 內——大致維持，非「提升」）",
    {x:0.42,y:calloutY+1.16,w:9.16,h:0.32,fontSize:10,color:C.textMid,align:"center",italic:true,fontFace:"Calibri"});
  addFooter(s);
}

/* ══════════ S9 評估結果 ══════════ */
{
  const s = pres.addSlide();
  s.background = {color:C.lightBg};
  addHeader(s,"評估結果","W-Score 階梯式排序：條款 grounding 全面領先","09");
  [{code:"sbert_only",w:"1.854",note:"純檢索",color:C.grey},
   {code:"no_rag",w:"1.912",note:"純 LLM",color:"1976D2"},
   {code:"metadata_rag",w:"2.755",note:"商品 metadata",color:C.midBg},
   {code:"pdf_rag",w:"2.892",note:"Full PDF RAG ✓",color:C.accentGreen}
  ].forEach((it,i)=>{
    const x=0.42+i*2.34;
    s.addShape(pres.shapes.RECTANGLE,{x,y:1.1,w:2.2,h:2.15,fill:{color:C.cardBg},line:{color:C.border,pt:1.5},shadow:makeShadow()});
    s.addShape(pres.shapes.RECTANGLE,{x,y:1.1,w:2.2,h:0.44,fill:{color:it.color},line:{color:it.color}});
    s.addText(it.code,{x:x+0.08,y:1.1,w:2.04,h:0.44,fontSize:10.5,bold:true,color:"FFFFFF",align:"center",valign:"middle",fontFace:"Consolas",margin:0});
    s.addText(it.w,{x:x+0.08,y:1.58,w:2.04,h:0.72,fontSize:34,bold:true,color:it.color,align:"center",valign:"middle",fontFace:"Calibri",margin:0});
    s.addText("/ 3.0",{x:x+0.08,y:2.3,w:2.04,h:0.24,fontSize:10,color:C.textMid,align:"center",fontFace:"Calibri",margin:0});
    s.addText(it.note,{x:x+0.08,y:2.58,w:2.04,h:0.45,fontSize:10.5,color:C.textMid,align:"center",valign:"top",fontFace:"Calibri",margin:0});
    if(i<3) s.addText("<",{x:x+2.18,y:1.75,w:0.2,h:0.5,fontSize:20,bold:true,color:C.grey,align:"center",valign:"middle",fontFace:"Calibri",margin:0});
  });
  [{t:"D2 可分解為兩個獨立貢獻：有商品資料（+0.96）+ 有條款原文（+0.56）",c:C.darkBg},
   {t:"pdf_rag 在 D1/D2/D3 三維度均達到或接近滿分，是唯一全面領先的策略（+51% vs no_rag）",c:C.accentGreen},
   {t:"三廠商評審一致（run 層級 Pearson r = 0.918–0.972），結論非單一模型偏好所致",c:C.midBg}
  ].forEach((ins,i)=>{
    const y=3.4+i*0.5;
    s.addShape(pres.shapes.RECTANGLE,{x:0.42,y,w:9.16,h:0.42,fill:{color:ins.c,transparency:92},line:{color:ins.c,pt:1}});
    s.addShape(pres.shapes.RECTANGLE,{x:0.42,y,w:0.1,h:0.42,fill:{color:ins.c},line:{color:ins.c}});
    s.addText("▸  "+ins.t,{x:0.6,y,w:8.9,h:0.42,fontSize:10.5,color:C.textDark,valign:"middle",fontFace:"Calibri",margin:0});
  });
  s.addText("36 筆回應構成：3 情境 × 4 技術策略 × 3 次重複 = 36；no_rag/metadata_rag/pdf_rag 由 Claude 生成，sbert_only 為確定性向量輸出",
    {x:0.42,y:4.92,w:9.16,h:0.28,fontSize:9.5,italic:true,color:C.textMid,align:"center",fontFace:"Calibri"});
  addFooter(s);
}

/* ══════════ S10 rubric 修正方法論 ══════════ */
{
  const s = pres.addSlide();
  s.background = {color:C.lightBg};
  addHeader(s,"評分 rubric 的發現與修正","一個有方法論價值的「誠實拒絕」評分缺口","10");
  s.addShape(pres.shapes.RECTANGLE,{x:0.42,y:1.06,w:9.16,h:1.0,fill:{color:C.cardBg},line:{color:C.red,pt:1.5},shadow:makeShadow()});
  s.addShape(pres.shapes.RECTANGLE,{x:0.42,y:1.06,w:0.12,h:1.0,fill:{color:C.red},line:{color:C.red}});
  s.addText([
    {text:"問題：",options:{bold:true,color:C.red,fontSize:12}},
    {text:"原始 D1 rubric 將「3 分」窄定義為「推薦具名商品」。S01 建築工人情境中，pdf_rag 讀到條款、",options:{color:C.textDark,fontSize:11}},
    {text:"正確判斷該商品不承保建築工人（5–6 類職業）並誠實拒絕——卻被評為與「無方向含糊回應」同樣的 2 分。",options:{color:C.textDark,fontSize:11,breakLine:true}}
  ],{x:0.62,y:1.06,w:8.8,h:1.0,fontFace:"Calibri",valign:"middle",margin:0});
  s.addShape(pres.shapes.RECTANGLE,{x:0.42,y:2.22,w:9.16,h:0.86,fill:{color:C.cardBg},line:{color:C.accentGreen,pt:1.5},shadow:makeShadow()});
  s.addShape(pres.shapes.RECTANGLE,{x:0.42,y:2.22,w:0.12,h:0.86,fill:{color:C.accentGreen},line:{color:C.accentGreen}});
  s.addText([
    {text:"修正：",options:{bold:true,color:"005C47",fontSize:12}},
    {text:"D1=3 分新增獨立路徑——「依具體可查證限制（如職業類別）正確拒絕推薦」，對全部 36 筆以同一標準重評。",options:{color:C.textDark,fontSize:11}}
  ],{x:0.62,y:2.22,w:8.8,h:0.86,fontFace:"Calibri",valign:"middle",margin:0});
  [{t:"僅 pdf_rag 顯著上升",d:"+0.283；其餘三策略 ±0.12 內（抽樣波動）",c:C.darkBg},
   {t:"評審一致性大致維持",d:"r 0.92–0.97 區間，變動 ±0.03 內",c:C.accentGreen},
   {t:"非調權重、非挑著改",d:"全程同一把尺、可重現（附錄 C）",c:C.midBg}
  ].forEach((v,i)=>{
    const x=0.42+i*3.1;
    s.addShape(pres.shapes.RECTANGLE,{x,y:3.24,w:2.9,h:1.3,fill:{color:v.c,transparency:90},line:{color:v.c,pt:1}});
    s.addText(v.t,{x:x+0.16,y:3.36,w:2.6,h:0.5,fontSize:11.5,bold:true,color:C.textDark,fontFace:"Calibri",valign:"top",margin:0});
    s.addText(v.d,{x:x+0.16,y:3.88,w:2.6,h:0.6,fontSize:10,color:C.textMid,fontFace:"Calibri",valign:"top",margin:0});
  });
  s.addText("發現一個有趣的中間修正插曲：v2 版措辭曾誤令評審對 metadata_rag 套用過嚴標準（W 2.729→2.468），釐清路徑(a)(b)邊界後（v3）恢復為 2.755——完整記錄於附錄 C",
    {x:0.42,y:4.7,w:9.16,h:0.5,fontSize:9.5,italic:true,color:C.textMid,align:"center",fontFace:"Calibri"});
  addFooter(s);
}

/* ══════════ S11 補充：3×4 矩陣 ══════════ */
{
  const s = pres.addSlide();
  s.background = {color:C.lightBg};
  addHeader(s,"補充分析：3×4 生成模型 × 文件策略矩陣","新增混淆變因控制組，拆解「候選商品數」與「全文 vs 切割」","11");
  const head=["生成模型","全文","單一商品切割","Docling 切割","切割+profile"];
  const cw=[2.0,1.7,1.95,1.75,1.78], x0=0.36, y0=1.1;
  let cx=x0;
  head.forEach((h,j)=>{
    s.addShape(pres.shapes.RECTANGLE,{x:cx,y:y0,w:cw[j],h:0.56,fill:{color:C.darkBg},line:{color:"FFFFFF",pt:1}});
    s.addText(h,{x:cx,y:y0,w:cw[j],h:0.56,fontSize:10,bold:true,color:"FFFFFF",align:"center",valign:"middle",fontFace:"Calibri",margin:0});
    cx+=cw[j];
  });
  const data=[
    ["Claude","2.959","2.952","2.892","2.870"],
    ["GPT-4o","2.788","2.788","2.765","2.678"],
    ["Gemini","3.000","2.899","2.870","2.910"],
    ["三模型平均","2.916","2.880","2.842","2.819"],
  ];
  data.forEach((row,i)=>{
    cx=x0; const y=y0+0.56+i*0.46; const isAvg=i===3;
    row.forEach((cell,j)=>{
      const hi = (i===1 && (j===1||j===2));
      s.addShape(pres.shapes.RECTANGLE,{x:cx,y,w:cw[j],h:0.46,fill:{color:hi?"FFF4D6":(isAvg?"EAF2F7":C.cardBg)},line:{color:C.border,pt:1}});
      s.addText(cell,{x:cx,y,w:cw[j],h:0.46,fontSize:10.5,bold:(j===0||isAvg||hi),color:hi?"92400E":C.textDark,align:j===0?"left":"center",valign:"middle",fontFace:"Calibri",margin:j===0?{left:0.1}:0});
      cx+=cw[j];
    });
  });
  s.addShape(pres.shapes.RECTANGLE,{x:0.36,y:3.35,w:9.28,h:1.1,fill:{color:C.cardBg},line:{color:C.accent,pt:1.5},shadow:makeShadow()});
  s.addText([
    {text:"關鍵發現：候選商品數 > 全文 vs 切割。",options:{bold:true,color:C.darkBg,fontSize:12,breakLine:true}},
    {text:"GPT-4o 上「全文」與「單一商品切割」W-Score 完全相同（2.788＝2.788）——兩者候選商品數同為 1，差異僅在全文 vs 切割。原先觀察到的「全文優勢」實質上由候選商品數驅動，而非全文呈現方式。",options:{color:C.textDark,fontSize:10.5}}
  ],{x:0.5,y:3.4,w:9.0,h:1.0,fontFace:"Calibri",valign:"middle",margin:0});
  s.addText("metadata 層（BGE-M3+BM25）與條款層（MiniLM）使用不同嵌入模型，為已揭露之方法論限制，未來建議統一模型家族並導入 re-ranking",
    {x:0.36,y:4.62,w:9.28,h:0.5,fontSize:9.5,italic:true,color:C.textMid,align:"center",fontFace:"Calibri"});
  addFooter(s);
}

/* ══════════ S12 治理與倫理（NEW） ══════════ */
{
  const s = pres.addSlide();
  s.background = {color:C.lightBg};
  addHeader(s,"治理與倫理討論","超越免責聲明：三項與近期文獻直接相關的治理議題","12");
  [{n:"01",t:"責任歸屬與防止不當銷售",ref:"Erlei & Meub, 2026",
    body:"信任財市場研究顯示：無責任規則時，LLM 專家可能傾向欺瞞消費者；導入責任歸屬可恢復誠實與市場參與。本系統需明確界定錯誤建議責任歸屬、申訴處理機制，而非僅靠免責聲明。",color:C.darkBg},
   {n:"02",t:"資訊輸出與自主行動分離",ref:"Zhu, 2026",
    body:"Agentic AI 風險（prompt injection、模型漂移、依賴失效）源於系統執行自主行動。本系統定位為僅提供資訊的顧問、不執行自主投保，是降低此類風險的設計選擇，仍須建置版本鎖定與稽核紀錄。",color:C.midBg},
   {n:"03",t:"個人化記憶的權力不對稱",ref:"Dorri & Zwick, 2025",
    body:"AI 可大規模長期保存用戶互動歷史，形成用戶無法對等掌握的結構性失衡。Profile-Augmented 模式應實作「設計式遺忘」（限制保存期限）、對稱的用戶存取與刪除控制，符合個資法要求。",color:C.accentGreen}
  ].forEach((item,i)=>{
    const y=1.08+i*1.42;
    s.addShape(pres.shapes.RECTANGLE,{x:0.42,y,w:9.16,h:1.3,fill:{color:C.cardBg},line:{color:C.border,pt:1},shadow:makeShadow()});
    s.addShape(pres.shapes.RECTANGLE,{x:0.42,y,w:0.62,h:1.3,fill:{color:item.color},line:{color:item.color}});
    s.addText(item.n,{x:0.42,y,w:0.62,h:1.3,fontSize:22,bold:true,color:"FFFFFF",align:"center",valign:"middle",fontFace:"Calibri",margin:0});
    s.addText(item.t,{x:1.2,y:y+0.08,w:6.0,h:0.34,fontSize:13,bold:true,color:C.textDark,fontFace:"Calibri",margin:0});
    s.addText(item.ref,{x:7.3,y:y+0.1,w:2.18,h:0.3,fontSize:9,italic:true,color:item.color,align:"right",fontFace:"Calibri",margin:0});
    s.addText(item.body,{x:1.2,y:y+0.42,w:8.2,h:0.82,fontSize:10.5,color:C.textMid,fontFace:"Calibri",valign:"top",margin:0});
  });
  addFooter(s);
}

/* ══════════ S13 研究限制 ══════════ */
{
  const s = pres.addSlide();
  s.background = {color:C.lightBg};
  addHeader(s,"研究限制","五項需要正面揭露的根本限制","13");
  [["01","缺乏人類專家基準驗證","LLM-as-Judge 非保險專業客觀標準，需持照從業人員比對"],
   ["02","LLM-as-Judge 潛在偏差","位置/冗長偏差固有限制；D2/D3 信度（α=0.73–0.78）低於 D1/W-Score"],
   ["03","評估情境規模有限","僅 3 個情境，難以涵蓋市場需求全部多樣性"],
   ["04","統計推論力有限","N=36，未做顯著性檢定；策略間微小差距（2.916 vs 2.880）待驗證"],
   ["05","商品資料集代表性未知","780 筆逐筆爬取，占市場實際比例未知，外部效度受限"]
  ].forEach((it,i)=>{
    const col = i%2, row = Math.floor(i/2);
    const x = 0.42+col*4.68, y = 1.1+row*1.32;
    const w = i===4 ? 9.16 : 4.5;
    s.addShape(pres.shapes.RECTANGLE,{x,y,w,h:1.18,fill:{color:C.cardBg},line:{color:C.border,pt:1},shadow:makeShadow()});
    s.addShape(pres.shapes.RECTANGLE,{x,y,w:0.5,h:1.18,fill:{color:C.red},line:{color:C.red}});
    s.addText(it[0],{x,y,w:0.5,h:1.18,fontSize:15,bold:true,color:"FFFFFF",align:"center",valign:"middle",fontFace:"Calibri",margin:0});
    s.addText(it[1],{x:x+0.62,y:y+0.1,w:w-0.74,h:0.3,fontSize:11.5,bold:true,color:C.textDark,fontFace:"Calibri",margin:0});
    s.addText(it[2],{x:x+0.62,y:y+0.42,w:w-0.74,h:0.7,fontSize:10,color:C.textMid,fontFace:"Calibri",valign:"top",margin:0});
  });
  addFooter(s);
}

/* ══════════ S14 未來研究方向 ══════════ */
{
  const s = pres.addSlide();
  s.background = {color:C.lightBg};
  addHeader(s,"未來研究方向","八個方向深化本研究的初步發現","14");
  const items = [
    "表格內部切割優化：row-level 切割策略，評估能否使 D2 逼近 3 分",
    "擴大評審基準：引入持照保險從業人員作為人類評審基準",
    "Profile-Augmented 正式消融：分離查詢擴增與檢索品質混淆變項",
    "D3 系統提示詞優化：評估「主動揭露」的可提升上限",
    "驗證誠實拒絕 rubric 普遍適用性：壓力測試路徑(b)判準",
    "全文 vs 切割在大規模語料的可行性邊界（780 筆規模）",
    "統一檢索堆疊 + RAGAS/ARES 標準化指標交叉驗證",
    "擴大樣本支援統計推論：30–50 情境、配對檢定、效果量",
  ];
  items.forEach((t,i)=>{
    const col=i%2, row=Math.floor(i/2);
    const x=0.42+col*4.68, y=1.08+row*1.0;
    s.addShape(pres.shapes.RECTANGLE,{x,y,w:4.5,h:0.88,fill:{color:C.cardBg},line:{color:C.border,pt:1}});
    s.addShape(pres.shapes.RECTANGLE,{x,y,w:0.42,h:0.88,fill:{color:C.accent},line:{color:C.accent}});
    s.addText((i+1).toString(),{x,y,w:0.42,h:0.88,fontSize:14,bold:true,color:"FFFFFF",align:"center",valign:"middle",fontFace:"Calibri",margin:0});
    s.addText(t,{x:x+0.54,y,w:3.86,h:0.88,fontSize:9.5,color:C.textDark,fontFace:"Calibri",valign:"middle",margin:0});
  });
  addFooter(s);
}

/* ══════════ S15 結論 ══════════ */
{
  const s = pres.addSlide();
  s.background = {color:C.darkBg};
  s.addShape(pres.shapes.RECTANGLE,{x:0,y:0,w:0.28,h:5.625,fill:{color:C.accent},line:{color:C.accent}});
  s.addShape(pres.shapes.RECTANGLE,{x:7.6,y:0,w:2.4,h:5.625,fill:{color:"0D4A6A"},line:{color:"0D4A6A"}});
  s.addText("結論",{x:0.65,y:0.28,w:6.8,h:0.6,fontSize:26,bold:true,color:C.textLight,fontFace:"Calibri",margin:0});
  s.addText("RAG 條款 grounding 使 AI 保險建議可信、可溯源",{x:0.65,y:0.92,w:6.8,h:0.4,fontSize:14,color:C.accent,fontFace:"Calibri",margin:0});
  [{n:"01",t:"四技術策略系統性比較，pdf_rag 條款 grounding 全面領先（2.892/3.0），四種權重方案下結論均穩健",c:C.accent},
   {n:"02",t:"檢索與 LLM 推理各有不可替代貢獻；D2 可分解為「有資料」與「有條款」兩個獨立槓桿",c:"A8DAEC"},
   {n:"03",t:"AHP 權重以法規錨定順序、誠實界定 CR；補充 Kendall's W／Krippendorff's α 完整呈現信度分層",c:C.accentGreen},
   {n:"04",t:"發現並修正 LLM-as-Judge 對「誠實拒絕」的評分缺口，誠實報告修正前後一致性「大致維持」",c:"93C5FD"},
   {n:"05",t:"納入治理／倫理討論（責任歸屬、agentic 風險分離、記憶權力不對稱），回應審查意見",c:C.purple}
  ].forEach((it,i)=>{
    const y=1.36+i*0.74;
    s.addShape(pres.shapes.RECTANGLE,{x:0.65,y,w:6.8,h:0.64,fill:{color:"FFFFFF",transparency:94},line:{color:"FFFFFF",pt:0.5}});
    s.addText(it.n,{x:0.78,y,w:0.5,h:0.64,fontSize:15,bold:true,color:it.c,fontFace:"Calibri",valign:"middle",margin:0});
    s.addText(it.t,{x:1.3,y,w:6.0,h:0.64,fontSize:10,color:C.textLight,fontFace:"Calibri",valign:"middle",margin:0});
  });
  s.addShape(pres.shapes.RECTANGLE,{x:0,y:5.1,w:10,h:0.525,fill:{color:"061E2E"},line:{color:"061E2E"}});
  s.addText("研討會報告　|　2026",{x:0.65,y:5.1,w:9,h:0.525,fontSize:13,color:"6B9EB5",valign:"middle",fontFace:"Calibri",margin:0});
}

pres.writeFile({fileName:"presentation_final.pptx"}).then(()=>console.log("Done: presentation_final.pptx")).catch(e=>console.error(e));
