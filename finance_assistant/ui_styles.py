"""Understated review desk styling; preserve the reference layout."""

CSS = """
<style>
.stApp {
  --desk-bg:#f5f6f8; --desk-ink:#252b34; --desk-muted:#707986;
  --desk-line:#dfe3e8; --desk-accent:#40546d;
  --desk-high:#af443e; --desk-medium:#946e35; --desk-low:#687787;
  background:var(--desk-bg)!important;color:var(--desk-ink)!important;color-scheme:light!important;
  font-family:"Segoe UI","Microsoft YaHei",sans-serif;
}
[data-testid="stAppViewContainer"],[data-testid="stMain"],[data-testid="stHeader"]{background:#f5f6f8!important;color:#252b34!important}
.block-container{max-width:1510px;padding:3.6rem 2.6rem 2.5rem!important}
.stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp [data-testid="stMarkdownContainer"],.stApp [data-testid="stWidgetLabel"],.stApp [data-testid="stWidgetLabel"] p{color:var(--desk-ink)!important}
.stApp [data-testid="stCaptionContainer"],.stApp [data-testid="stCaptionContainer"] p{color:var(--desk-muted)!important}
.stApp a{color:var(--desk-accent)}

/* Navigation retains the reference sidebar and history placement. */
[data-testid="stSidebar"]{background:#1d2735!important;color:#d5dbe3!important;min-width:264px;max-width:264px}
[data-testid="stSidebarContent"]{background:#1d2735!important;padding:1.6rem 1.1rem}
.stApp [data-testid="stSidebar"] [data-testid="stMarkdownContainer"],.stApp [data-testid="stSidebar"] h3,.stApp [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,.stApp [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p{color:#cbd2dc!important}
.brand{font-size:25px;font-weight:650;color:#fff;margin:2px 8px 5px;letter-spacing:.5px}
.brand-sub{font-size:12px;color:#9aa7b9;margin:0 8px 29px}
.nav-label{font-size:12px;color:#99a6b8;margin:27px 9px 12px}
.nav-empty{color:#a5afbd;font-size:12px;margin:15px 9px;line-height:1.8}
.stApp [data-testid="stSidebar"] button{background:transparent!important;border:1px solid transparent!important;color:#d5dbe3!important;text-align:left;box-shadow:none!important;border-radius:5px!important}
.stApp [data-testid="stSidebar"] button p{color:inherit!important;font-size:13px!important}
.stApp [data-testid="stSidebar"] button:hover{background:#293649!important;border-color:#3a485c!important}
.stApp [data-testid="stSidebar"] button[kind="primary"]{background:#40546d!important;color:#fff!important;border-color:#5b6c82!important}
.stApp [data-testid="stSidebar"] [data-testid="stExpander"]{background:#253142!important;border-color:#3a4657!important}
.stApp [data-testid="stSidebar"] [data-testid="stExpander"] summary,.stApp [data-testid="stSidebar"] [data-testid="stExpander"] details{color:#d5dbe3!important;background:#253142!important}
.st-key-sidebar_footer{margin-top:95px!important;border-top:1px solid #3a4657;padding-top:18px}
.sidebar-stat{font-size:12px;color:#a4afbe;margin:0 9px 12px}
.sidebar-identity{color:#99a6b8;font-size:11px;margin:0 9px;line-height:1.8}

/* Document header and native controls. */
.case-header{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--desk-line);padding:4px 0 24px;margin-bottom:7px;gap:20px}
.case-title{font-size:20px;font-weight:650;color:var(--desk-ink);line-height:1.5}
.case-meta{font-size:12px;color:var(--desk-muted);margin-top:7px}
.case-status{border:1px solid #dce1e7;color:#566273;background:#edf0f4;border-radius:5px;padding:7px 13px;white-space:nowrap;font-size:12px}
.stApp button{background:#fff!important;color:#3c4756!important;border:1px solid #d5dbe3!important;border-radius:5px!important;box-shadow:none!important;font-size:12px!important}
.stApp button p{color:inherit!important}
.stApp button:hover{border-color:#8d9bad!important;background:#f4f6f8!important}
.stApp button[kind^="primary"]{background:var(--desk-accent)!important;color:#fff!important;border-color:var(--desk-accent)!important}
.stApp button[kind^="primary"]:hover{background:#33465e!important;border-color:#33465e!important}
.stApp button[kind^="primary"] p{color:#fff!important}
.stApp button:disabled{opacity:.5!important}
.stApp button:focus-visible,.stApp [role="tab"]:focus-visible{outline:2px solid #8a99ad!important;outline-offset:2px}
.stApp [role="tab"]{background:transparent!important;border:none!important;border-radius:0!important;color:#717a87!important;padding:12px 13px!important;font-size:13px!important}
.stApp [role="tab"][aria-selected="true"]{color:#33465e!important}
.stApp [role="tab"] p{color:inherit!important}
.stApp [role="tab"] .react-aria-SelectionIndicator{background:#40546d!important}
.stApp [data-baseweb="tab-highlight"]{background:#40546d!important}
.stApp [data-baseweb="tab-border"]{background:#dfe3e8!important}
.stApp [data-testid="stTextArea"] textarea,.stApp [data-testid="stTextInput"] input,.stApp [data-baseweb="textarea"],.stApp [data-baseweb="input"],.stApp [data-baseweb="base-input"]{background:#f8f9fb!important;color:#252b34!important;caret-color:#252b34!important;border-radius:5px!important}
.stApp textarea::placeholder,.stApp input::placeholder{color:#838d9a!important;opacity:1!important}
.stApp [data-baseweb="textarea"]:focus-within,.stApp [data-baseweb="input"]:focus-within{border-color:#6f8096!important}
.stApp [data-testid="stForm"]{background:#fff!important;border:1px solid var(--desk-line)!important;border-radius:7px!important;padding:18px!important}
.stApp [data-testid="stFileUploaderDropzone"]{background:#f8f9fb!important;color:#687483!important;border:1px dashed #cbd2db!important;border-radius:5px!important}
.stApp [data-testid="stFileUploaderDropzone"] small,.stApp [data-testid="stFileUploaderDropzone"] span{color:#687483!important}
.stApp [data-testid="stExpander"]{background:#fff;border-color:var(--desk-line);border-radius:6px}
.stApp [data-testid="stExpander"] summary,.stApp [data-testid="stExpander"] details{color:#4e5b6c!important;background:#fff!important}
.stApp [data-testid="stStatusWidget"] svg,.stApp [data-testid="stStatusWidget"] [data-testid="stIconMaterial"]{color:#566b84!important}
.stApp [data-testid="stAlertContainer"]{border-radius:5px}
.stApp [data-testid="stAlertContentSuccess"]{color:#40546d!important;background:#edf0f4!important}

/* Conversation and review findings retain their original positions. */
.welcome{background:#fff;border:1px solid var(--desk-line);border-radius:7px;padding:30px;margin:19px 0 25px}
.welcome h1{font-size:25px!important;font-weight:600!important;line-height:1.5!important;padding:0 0 9px!important;margin:0!important}
.welcome p{color:#707986;font-size:13px;line-height:1.9;max-width:650px;margin:0}
.user-row{display:flex;justify-content:flex-end;align-items:flex-start;gap:12px;margin:22px 0 28px}
.user-bubble{background:#edf0f5;border:1px solid #e1e5eb;border-radius:7px;color:#354253;padding:15px 20px;max-width:75%;font-size:13px;line-height:1.8}
.avatar{width:35px;height:35px;flex:0 0 35px;border-radius:5px;display:grid;place-items:center;font-size:11px;font-weight:600;background:#e8ecf1;color:#56677b}
.avatar.ai{background:#e7ebf0;color:#4d6078}
.assistant-row{display:flex;gap:14px;align-items:flex-start;margin:5px 0 20px}
.assistant-title{font-size:14px;font-weight:600;line-height:1.7;color:#29323f}
.assistant-sub{font-size:12px;color:#737e8d;margin-top:5px;line-height:1.8}
[class*="st-key-finding_"]{background:#fff!important;border:1px solid var(--desk-line);border-radius:7px;padding:21px 24px;margin-bottom:16px}
[class*="st-key-finding_high_"]{border-left:3px solid var(--desk-high)}
[class*="st-key-finding_medium_"]{border-left:3px solid var(--desk-medium)}
[class*="st-key-finding_low_"]{border-left:3px solid var(--desk-low)}
.finding-head{display:flex;align-items:center;gap:13px;margin-bottom:13px}
.finding-title{font-weight:600;color:#29323f;font-size:15px;line-height:1.6}
.badge{display:inline-block;border-radius:4px;padding:5px 10px;font-size:11px;font-weight:500;white-space:nowrap}
.badge.high{color:var(--desk-high);background:#f8eae8}
.badge.medium{color:var(--desk-medium);background:#f5efe5}
.badge.low{color:#5f6e7e;background:#eaf0f4}
.badge.unknown{color:#747d89;background:#f0f2f5}
.finding-reason{color:#566273;font-size:13px;line-height:1.9;margin-bottom:14px}
.recommendation{color:#405168;font-size:12px;line-height:1.9;margin:13px 0 3px;padding:10px 12px;background:#f2f4f7;border-radius:4px}
.quote{padding:13px 15px;border-left:3px solid #cfd6df;background:#f6f7f9;color:#596575;font-size:12px;line-height:1.9}

/* Report layout: document excerpts on the left, analysis on the right. */
.section-label{font-size:12px;font-weight:500;color:#657182;margin:4px 0 17px}
.paper{background:#fff;border:1px solid var(--desk-line);border-radius:7px;overflow:hidden;min-height:500px}
.paper-head{background:#263345;color:#fff;padding:21px 25px;display:flex;justify-content:space-between;gap:15px;font-size:13px;font-weight:600}
.paper-head span{color:#c1cad6;font-size:11px;font-weight:400}
.paper-body{padding:24px}
.paper-excerpt{border-left:3px solid var(--desk-high);background:#fbf0ee;padding:15px 17px;border-radius:4px;margin-bottom:17px}
.paper-excerpt.medium{background:#f8f3ea;border-color:var(--desk-medium)}
.paper-excerpt.low{background:#f0f3f6;border-color:var(--desk-low)}
.paper-excerpt.unknown{background:#f2f3f5;border-color:#939dab}
.paper-excerpt strong{font-size:13px;color:#8e403c;font-weight:600}
.paper-excerpt.medium strong{color:#866430}
.paper-excerpt.low strong{color:#576779}
.paper-excerpt.unknown strong{color:#737d8b}
.paper-excerpt p{font-size:12px;color:#596575;line-height:1.8;margin:9px 0 0}
.paper-foot{font-size:11px;color:#7a8594;border-top:1px solid #e6e9ee;margin-top:28px;padding-top:15px;line-height:1.9}
.metric-card{background:#fff;border:1px solid var(--desk-line);border-radius:7px;padding:21px 23px;min-height:270px}
.metric-value{font-size:41px;font-weight:650;line-height:1.3;color:var(--desk-high);margin:18px 0 12px}
.metric-note{font-size:11px;color:#7a8594;line-height:1.8}
.distribution-row{display:flex;gap:13px;align-items:center;margin:24px 0;font-size:12px;color:#657182}
.distribution-label{width:38px;flex:0 0 38px;white-space:nowrap}
.bar-track{height:8px;background:#edf0f3;border-radius:3px;flex:1;overflow:hidden}
.bar{height:8px;border-radius:3px;background:#939dab}
.bar.high{background:#b65a53}.bar.medium{background:#b09164}.bar.low{background:#8a97a6}
.distribution-count{width:30px;text-align:right;color:#3c4756}
.top-findings{background:#fff;border:1px solid var(--desk-line);border-radius:7px;padding:23px;margin-top:18px}
.top-row{display:flex;gap:13px;align-items:flex-start;padding:18px 0;border-bottom:1px solid #e9ecf0}
.top-row:last-child{border-bottom:none}
.top-text{font-size:13px;color:#303b4a;font-weight:600;line-height:1.8}
.top-advice{font-size:12px;color:#737e8d;font-weight:400;margin-top:6px;line-height:1.8}
.empty-state{padding:60px 20px;text-align:center;color:#7a8594;font-size:13px;line-height:2;background:#fff;border:1px dashed #d4dbe3;border-radius:7px;margin:20px 0}
.workspace-foot{font-size:11px;color:#7a8594;margin:18px 0;line-height:1.9}
@media(max-width:900px){.block-container{padding:1rem!important}.case-title{font-size:17px}.welcome{padding:22px}.welcome h1{font-size:22px!important}.user-bubble{max-width:90%}[class*="st-key-finding_"]{padding:16px}.metric-card{padding:17px}.paper-body{padding:16px}}
</style>
"""
