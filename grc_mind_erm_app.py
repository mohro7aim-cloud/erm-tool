# -*- coding: utf-8 -*-
"""
GRC MIND | أداة إدارة المخاطر المؤسسية (ERM) وفق ISO 31000:2018
شركة تأمين ممتلكات مصرية

التشغيل:
    pip install streamlit pandas plotly openpyxl
    streamlit run grc_mind_erm_app.py
"""
import io
import os
import pickle

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ───────────────────────── إعداد الصفحة ─────────────────────────
st.set_page_config(
    page_title="GRC MIND | إدارة المخاطر المؤسسية",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

TODAY = pd.Timestamp.today().normalize()
SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "erm_data.pkl")

_VER = tuple(int(x) for x in st.__version__.split(".")[:2] if x.isdigit())
STRETCH = {"width": "stretch"} if _VER >= (1, 50) else {"use_container_width": True}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');
html, body, .stApp, button, input, textarea, select { font-family: 'Cairo','Segoe UI',Tahoma,sans-serif !important; }
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMarkdownContainer"], [data-testid="stMetric"],
.stAlert, label, .stTabs, [data-testid="stExpander"], [data-testid="stCaptionContainer"] { direction: rtl; text-align: right; }
.block-container { padding-top: 1.2rem; max-width: 1500px; }
.hero { background: linear-gradient(120deg,#0b2a4a 0%,#145c7a 60%,#1b8a8f 100%); color:#fff; padding: 22px 28px;
        border-radius: 16px; margin-bottom: 14px; }
.hero h1 { margin:0; font-size: 1.9rem; font-weight: 800; color:#fff; }
.hero p { margin: 4px 0 0 0; opacity:.9; font-size: 1rem; }
.sec-head { border-right: 6px solid #145c7a; padding: 6px 14px; margin: 6px 0 14px 0; background:#f1f6f9; border-radius: 8px; }
.sec-head h2 { margin:0; font-size:1.35rem; color:#0b2a4a; }
.sec-head span { color:#4a6572; font-size:.92rem; }
.card { background:#fff; border:1px solid #e1e8ed; border-radius:14px; padding:14px 16px; height:100%;
        box-shadow:0 1px 4px rgba(11,42,74,.06); }
.card h4 { margin:0 0 6px 0; color:#145c7a; font-size:1.02rem; }
.card p { margin:0; color:#4a5a66; font-size:.88rem; line-height:1.7; }
[data-testid="stMetric"] { background:#f7fafc; border:1px solid #e1e8ed; border-radius:12px; padding:10px 14px; }
div.stButton > button { border-radius: 10px; font-weight: 600; width:100%; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ───────────────────────── ثوابت ─────────────────────────
CATS = ["استراتيجية", "مالية", "تشغيلية", "سمعة", "امتثال", "فرص"]
TYPES = ["تهديد", "فرصة"]
TREAT_OPTS = ["تخفيف", "نقل / إعادة تأمين", "تجنب", "قبول", "استغلال الفرصة"]
TREAT_STATUS = ["لم تبدأ", "قيد التنفيذ", "مكتملة"]
IMPL = ["مكتمل", "قيد التطبيق", "غير مطبق"]
FREQS = ["شهرية", "ربع سنوية", "نصف سنوية", "سنوية"]
FREQ_DAYS = {"شهرية": 30, "ربع سنوية": 91, "نصف سنوية": 182, "سنوية": 365}
DEFAULT_FREQ = {"مرتفع": "شهرية", "متوسط": "ربع سنوية", "منخفض": "سنوية"}
LEVEL_COLOR = {"مرتفع": "#d93025", "متوسط": "#f4b400", "منخفض": "#2e9e5b"}
ROLES = ["مجلس الإدارة", "لجنة المخاطر", "الرئيس التنفيذي", "مدير إدارة المخاطر", "الاكتتاب", "المطالبات",
         "المالية والاستثمار", "الاكتواري", "الامتثال", "تقنية المعلومات", "إعادة التأمين", "المراجعة الداخلية"]
RACI_VALUES = ["", "A", "R", "A/R", "C", "I"]

PAGES = [
    ("home", "🏠 الغلاف"), ("fw", "5 | الإطار المؤسسي"), ("ctx", "6.3.3 | السياق"),
    ("crit", "6.3.4 | معايير المخاطر"), ("reg", "6.4 | سجل المخاطر"), ("trt", "6.5 | المعالجة"),
    ("raci", "5.4.3 | RACI"), ("mon", "6.6 | المراقبة"), ("com", "6.2/6.7 | الإبلاغ"),
    ("mat", "🎯 النضج المؤسسي"), ("dash", "📊 لوحة التحكم"),
]


# ───────────────────────── الدوال المساعدة العامة ─────────────────────────
def thresholds():
    t = st.session_state.thr
    return t["med"], t["high"]


def level_of(score):
    med, high = thresholds()
    return "مرتفع" if score >= high else ("متوسط" if score >= med else "منخفض")


def zone_of(score):
    med, high = thresholds()
    return 2 if score >= high else (1 if score >= med else 0)


def section(title, clause, desc=""):
    st.markdown(
        f"<div class='sec-head'><h2>{title} <span>— {clause}</span></h2><span>{desc}</span></div>",
        unsafe_allow_html=True,
    )


def apply_delta(base, delta):
    """تطبيق تعديلات st.data_editor (edited / added / deleted) على الجدول الأساسي."""
    base = base.reset_index(drop=True).copy()
    for i, changes in (delta or {}).get("edited_rows", {}).items():
        idx = base.index[int(i)]
        for col, val in changes.items():
            if col in base.columns:
                base[col] = base[col].astype(object)
                base.at[idx, col] = val
    dele = (delta or {}).get("deleted_rows", [])
    if dele:
        base = base.drop(base.index[dele])
    adds = (delta or {}).get("added_rows", [])
    if adds:
        base = pd.concat([base, pd.DataFrame(adds)], ignore_index=True)
    return base.reset_index(drop=True)


def table(name, post=None, dynamic=False, disabled=(), config=None, height=None):
    """محرر جدول تفاعلي: الحالة الأساسية محفوظة في session_state وتُحدَّث عبر callback."""
    ver = st.session_state.setdefault(f"{name}_v", 0)
    key = f"{name}_ed_{ver}"

    def cb():
        d = apply_delta(st.session_state[name], st.session_state.get(key, {}))
        st.session_state[name] = post(d) if post else d
        st.session_state[f"{name}_v"] += 1

    kw = {"height": height} if height else {}
    st.data_editor(
        st.session_state[name], key=key, on_change=cb, hide_index=True,
        num_rows="dynamic" if dynamic else "fixed", disabled=list(disabled),
        column_config=config or {}, **STRETCH, **kw,
    )


def show_df(df, style_col=None):
    if style_col and style_col in df.columns:
        def colr(v):
            return {"مرتفع": "background-color:#f8d7da;color:#7a1c24",
                    "متوسط": "background-color:#fff3cd;color:#7a5b00",
                    "منخفض": "background-color:#d4edda;color:#17572b"}.get(v, "")
        sty = df.style
        sty = sty.map(colr, subset=[style_col]) if hasattr(sty, "map") else sty.applymap(colr, subset=[style_col])
        st.dataframe(sty, hide_index=True, **STRETCH)
    else:
        st.dataframe(df, hide_index=True, **STRETCH)


def plot(fig, key):
    fig.update_layout(font=dict(family="Cairo, Tahoma, sans-serif"), margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, key=key, **STRETCH)


# ───────────────────────── البيانات الافتراضية ─────────────────────────
def d_fw():
    rows = [
        ("5.1", "القيادة والالتزام", "الأحكام العامة: ضمان تكامل إدارة المخاطر في كل أنشطة الشركة", "مجلس الإدارة", "قيد التطبيق", "اعتماد ميثاق إدارة المخاطر قيد المراجعة"),
        ("5.2", "القيادة والالتزام", "التزام الإدارة العليا ومجلس الإدارة بسياسة وشهية مخاطر معتمدة", "الرئيس التنفيذي", "مكتمل", "سياسة معتمدة من المجلس"),
        ("5.3", "التكامل", "دمج إدارة المخاطر في الحوكمة والاستراتيجية والتخطيط والعمليات", "مدير إدارة المخاطر", "قيد التطبيق", "دمج جزئي في دورة الاكتتاب"),
        ("5.4.1", "التصميم", "فهم المؤسسة وسياقها الداخلي والخارجي", "مدير إدارة المخاطر", "مكتمل", "راجع قسم السياق"),
        ("5.4.2", "التصميم", "توضيح التزام الإدارة بإدارة المخاطر (السياسة، الأهداف، شهية المخاطر)", "الرئيس التنفيذي", "مكتمل", ""),
        ("5.4.3", "التصميم", "تحديد الأدوار والسلطات والمسؤوليات والمساءلة", "مدير إدارة المخاطر", "قيد التطبيق", "مصفوفة RACI قيد الاستكمال"),
        ("5.4.4", "التصميم", "تخصيص الموارد (كوادر، أنظمة، ميزانية، تدريب)", "الرئيس التنفيذي", "قيد التطبيق", "نقص في الكوادر الاكتوارية"),
        ("5.4.5", "التصميم", "إنشاء قنوات الاتصال والاستشارة مع أصحاب المصلحة", "مدير إدارة المخاطر", "قيد التطبيق", ""),
        ("5.5", "التطبيق", "تطبيق الإطار: خطة زمنية، إشراك أصحاب المصلحة، تعديل العمليات", "مدير إدارة المخاطر", "غير مطبق", "بانتظار اعتماد خطة التطبيق"),
        ("5.6", "التقييم", "قياس أداء الإطار دورياً مقابل غرضه وخطط تنفيذه", "المراجعة الداخلية", "غير مطبق", ""),
        ("5.7.1", "التحسين", "التكيف مع التغيرات الداخلية والخارجية", "مدير إدارة المخاطر", "قيد التطبيق", ""),
        ("5.7.2", "التحسين", "التحسين المستمر لملاءمة الإطار وكفاءته وفعاليته", "لجنة المخاطر", "غير مطبق", ""),
    ]
    return pd.DataFrame(rows, columns=["البند", "المحور", "المتطلب", "المسؤول", "الحالة", "ملاحظات تنفيذية"])


CTX_COLS = ["العامل", "الوصف والأثر على الشركة", "طبيعة الأثر", "درجة التأثير", "ملاحظات"]


def d_ctx_ext():
    rows = [
        ("تشريعات وتعليمات الهيئة العامة للرقابة المالية (FRA)", "متطلبات الملاءة، الاحتياطيات الفنية، الإفصاح، التأمين الموحد وتعليمات الاستثمار", "تهديد", 5, "تعديلات متكررة تتطلب مرونة"),
        ("التضخم", "ارتفاع تكلفة الإصلاح والتعمير يرفع قيمة المطالبات ويُفاقم التأمين الناقص", "تهديد", 5, ""),
        ("سعر الصرف وانخفاض الجنيه", "ارتفاع تكلفة قطع الغيار والمعدات المستوردة وتأثر عقود إعادة التأمين بالعملة الأجنبية", "تهديد", 5, ""),
        ("الكوارث الطبيعية (سيول، زلازل)", "تعرض المدن الصناعية (10 رمضان، 6 أكتوبر، العبور) لتراكم خسائر كبيرة", "تهديد", 4, "تراكم جغرافي"),
        ("المنافسة في السوق المصري", "حرب أسعار وضغط على هوامش الاكتتاب من شركات محلية وفروع أجنبية", "تهديد", 4, ""),
        ("سوق إعادة التأمين العالمي وتصنيف المعيدين", "تقلب أسعار وطاقات إعادة التأمين وتأثر الثقة بتصنيف معيدي التأمين الدوليين", "تهديد", 4, "فرصة لتنويع المعيدين"),
    ]
    return pd.DataFrame(rows, columns=CTX_COLS)


def d_ctx_int():
    rows = [
        ("هيكل الاكتتاب والتسعير", "اعتماد قواعد اكتتاب وتعريفات موحدة وصلاحيات اكتتاب", "محايد", 4, ""),
        ("تركز محفظة الممتلكات", "تركز جغرافي في المدن الصناعية وتركز في قطاعات محددة", "تهديد", 4, ""),
        ("الأنظمة التقنية", "قدم أنظمة الإصدار والمطالبات وضعف التكامل", "تهديد", 4, "فرصة للتحول الرقمي"),
        ("الكوادر الاكتوارية", "نقص الخبرات الاكتوارية وهجرة الكفاءات", "تهديد", 4, ""),
        ("الثقافة المؤسسية للمخاطر", "مستوى وعي الموظفين بالمخاطر وتقبّل المساءلة", "محايد", 3, ""),
        ("الحوكمة وهيكل مجلس الإدارة", "وجود لجنة مخاطر ولجنة مراجعة ومدى استقلاليتها", "فرصة", 3, ""),
        ("المركز المالي وهامش الملاءة", "كفاية رأس المال والملاءة مقابل متطلبات FRA", "محايد", 5, ""),
        ("إدارة المطالبات", "سرعة التسوية وجودة التقدير وضوابط مكافحة الاحتيال", "تهديد", 4, ""),
        ("شبكة التوزيع والوسطاء", "الاعتماد على الوسطاء والبنوك وجودة التحصيل", "محايد", 3, ""),
        ("اتفاقيات إعادة التأمين وحدود الاحتفاظ", "هيكل المعاهدات الاتفاقية والاختيارية وحدود الاحتفاظ الصافي", "محايد", 5, ""),
    ]
    return pd.DataFrame(rows, columns=CTX_COLS)


def d_crit():
    rows = [
        (1, "مصفوفة الاحتمالية × الأثر (5×5)", "درجة الخطر = الاحتمالية (1–5) × الأثر (1–5) ومداها من 1 إلى 25", "6.3.4", False),
        (2, "مقياس الاحتمالية", "خمس درجات من نادر إلى شبه مؤكد مع تكرار متوقع لكل درجة", "6.3.4", False),
        (3, "مقياس الأثر", "خمس درجات من ضئيل إلى كارثي مرتبطة بنسبة من حقوق الملكية وبالأثر الرقابي والسمعة", "6.3.4", False),
        (4, "مستويات الخطر ومعايير القبول", "حدود (منخفض/متوسط/مرتفع) والإجراء المطلوب لكل مستوى", "6.3.4", False),
        (5, "حدود الاحتفاظ الصافي", "حد الاحتفاظ لكل خطر ولكل حدث (بما فيها الكوارث الطبيعية) وفق اتفاقيات إعادة التأمين", "6.3.4", False),
        (6, "شهية المخاطر وحدود التحمل", "اعتماد مجلس الإدارة للحدود القصوى للخسارة وملاءة الشركة", "5.4.2", False),
        (7, "معايير التصعيد والموافقة", "من يوافق على قبول الخطر المتبقي وأي مستوى يُصعَّد لمجلس الإدارة", "6.3.4", False),
    ]
    return pd.DataFrame(rows, columns=["م", "البند", "المعيار المعتمد", "المرجع", "معتمد"])


def d_scale_l():
    return pd.DataFrame([
        (1, "نادر", "أقل من مرة كل 20 سنة (< 5%)"),
        (2, "غير محتمل", "مرة كل 10–20 سنة (5–20%)"),
        (3, "محتمل", "مرة كل 3–10 سنوات (20–50%)"),
        (4, "مرجح", "مرة كل 1–3 سنوات (50–80%)"),
        (5, "شبه مؤكد", "سنوياً أو أكثر (> 80%)"),
    ], columns=["الدرجة", "الوصف", "التكرار / الاحتمال"])


def d_scale_i():
    return pd.DataFrame([
        (1, "ضئيل", "خسارة أقل من 0.5% من حقوق الملكية، دون أثر رقابي"),
        (2, "طفيف", "0.5%–2% من حقوق الملكية، ملاحظات رقابية بسيطة"),
        (3, "متوسط", "2%–5% من حقوق الملكية، تأثر سمعة محلي"),
        (4, "كبير", "5%–10% من حقوق الملكية، إجراءات رقابية من FRA"),
        (5, "كارثي", "أكثر من 10% من حقوق الملكية أو تهديد هامش الملاءة"),
    ], columns=["الدرجة", "الوصف", "المعيار المالي / التشغيلي / الرقابي"])


def d_retention():
    return pd.DataFrame([
        ("حريق وملحقاته", 10.0, 30.0, "قيم استرشادية — تُعتمد من لجنة المخاطر"),
        ("هندسي", 5.0, 15.0, ""),
        ("بحري وشحن", 3.0, 9.0, ""),
        ("كوارث طبيعية (سيول/زلازل)", 0.0, 50.0, "حد الاحتفاظ لكل حدث تجميعي"),
    ], columns=["الفرع / الخطر", "الاحتفاظ لكل خطر (مليون ج.م)", "الاحتفاظ لكل حدث (مليون ج.م)", "ملاحظات"])


def d_accept():
    return None  # يُحسب ديناميكياً


REG_COLS = ["المعرّف", "الفئة", "النوع", "الخطر / الفرصة", "الوصف", "الاحتمالية", "الأثر", "درجة الخطر", "المستوى", "مالك الخطر"]


def d_reg():
    rows = [
        ("مالية", "تهديد", "تراكم خسائر الكوارث الطبيعية بالمدن الصناعية", "سيول أو زلزال يؤثر على تجمع منشآت في 10 رمضان و6 أكتوبر ويتجاوز حدود الاحتفاظ", 3, 5, "المالية والاستثمار"),
        ("مالية", "تهديد", "التأمين الناقص (Under-insurance)", "انخفاض مبالغ التأمين عن القيمة الاستبدالية بسبب التضخم وانخفاض الجنيه", 5, 4, "الاكتتاب"),
        ("مالية", "تهديد", "مخاطر إعادة التأمين وتصنيف المعيدين", "خفض تصنيف معيدي التأمين الدوليين أو تعثرهم أو تحويل العملة", 2, 5, "إعادة التأمين"),
        ("امتثال", "تهديد", "عدم الالتزام بتعليمات الهيئة العامة للرقابة المالية FRA", "مخالفة متطلبات الملاءة والاحتياطيات والإفصاح والتقارير الدورية", 3, 4, "الامتثال"),
        ("مالية", "تهديد", "عدم كفاية الاحتياطيات الفنية", "ضعف تقدير المطالبات المتكبدة وغير المبلغ عنها (IBNR)", 3, 4, "الاكتواري"),
        ("مالية", "تهديد", "مخاطر الاستثمار وتقلب سعر الصرف", "خسائر على الأصول والالتزامات بالعملات الأجنبية وتقلب أسعار الفائدة", 4, 3, "المالية والاستثمار"),
        ("مالية", "تهديد", "مخاطر الائتمان وتحصيل الأقساط", "تأخر تحصيل أرصدة الوسطاء والعملاء ومديونيات المعيدين", 4, 3, "المالية والاستثمار"),
        ("تشغيلية", "تهديد", "ضعف الاكتتاب والتسعير", "قبول مخاطر بأسعار غير كافية أو دون معاينة فنية", 3, 4, "الاكتتاب"),
        ("تشغيلية", "تهديد", "بطء تسوية المطالبات وتضخم تكلفتها", "ارتفاع أسعار قطع الغيار ومواد البناء وتأخر المعاينة", 4, 3, "المطالبات"),
        ("تشغيلية", "تهديد", "الاحتيال في المطالبات", "مطالبات مبالغ فيها أو وهمية خاصة في الحريق والسرقة", 3, 3, "المطالبات"),
        ("تشغيلية", "تهديد", "تعطل الأنظمة والهجمات السيبرانية", "توقف أنظمة الإصدار أو المطالبات أو تسرب بيانات العملاء", 3, 4, "تقنية المعلومات"),
        ("تشغيلية", "تهديد", "نقص الكوادر الاكتوارية والفنية", "فقدان خبرات التسعير والمعايرة وهجرة الكفاءات", 4, 3, "الرئيس التنفيذي"),
        ("استراتيجية", "تهديد", "حرب الأسعار والمنافسة", "تخفيض الأسعار دون مبرر فني وتآكل هامش الاكتتاب", 4, 3, "الرئيس التنفيذي"),
        ("استراتيجية", "تهديد", "تركز المحفظة", "تركز في قطاعات أو مدن أو وسطاء أو عملاء كبار", 3, 4, "الاكتتاب"),
        ("سمعة", "تهديد", "تأخر سداد التعويضات", "شكاوى العملاء وتأثر سمعة الشركة والتصنيف", 3, 4, "المطالبات"),
        ("امتثال", "تهديد", "مكافحة غسل الأموال وتمويل الإرهاب", "عدم كفاية إجراءات العناية الواجبة وتقارير الاشتباه", 2, 4, "الامتثال"),
        ("فرص", "فرصة", "التحول الرقمي للإصدار والمطالبات", "خفض التكلفة وتحسين تجربة العميل وتوسيع قنوات البيع الرقمية", 4, 4, "تقنية المعلومات"),
        ("فرص", "فرصة", "نمو الطلب على تغطيات الممتلكات الصناعية والكوارث", "ارتفاع الوعي بعد الكوارث والتوسع الصناعي والمدن الجديدة", 3, 4, "الاكتتاب"),
        ("فرص", "فرصة", "إعادة هيكلة اتفاقيات إعادة التأمين", "تحسين شروط التغطية والتكلفة وتنويع المعيدين", 3, 3, "إعادة التأمين"),
    ]
    df = pd.DataFrame([(f"R-{i+1:02d}",) + r[:2 + 0] + r[2:] for i, r in enumerate(rows)],
                      columns=["المعرّف", "الفئة", "النوع", "الخطر / الفرصة", "الوصف", "الاحتمالية", "الأثر", "مالك الخطر"])
    return compute_register(df)


def compute_register(df):
    df = df.reset_index(drop=True).copy()
    for c in REG_COLS:
        if c not in df.columns:
            df[c] = None
    for c in ["المعرّف", "الخطر / الفرصة", "الوصف", "مالك الخطر"]:
        df[c] = df[c].fillna("").astype(str)
    df["الفئة"] = df["الفئة"].where(df["الفئة"].isin(CATS), "تشغيلية")
    df["النوع"] = df["النوع"].where(df["النوع"].isin(TYPES), "تهديد")
    opp = (df["النوع"] == "فرصة") | (df["الفئة"] == "فرص")
    df.loc[opp, "النوع"] = "فرصة"
    df.loc[opp, "الفئة"] = "فرص"
    for c in ["الاحتمالية", "الأثر"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(1).clip(1, 5).round().astype(int)
    used, n = set(df["المعرّف"].str.strip()), 1
    for i in df.index:
        if df.at[i, "المعرّف"].strip() == "":
            while f"R-{n:02d}" in used:
                n += 1
            df.at[i, "المعرّف"] = f"R-{n:02d}"
            used.add(df.at[i, "المعرّف"])
    df["درجة الخطر"] = df["الاحتمالية"] * df["الأثر"]
    df["المستوى"] = df["درجة الخطر"].map(level_of)
    return df[REG_COLS]


def reg_names():
    reg = st.session_state.reg
    return dict(zip(reg["المعرّف"], reg["الخطر / الفرصة"]))


TR_COLS = ["المعرّف", "الخطر / الفرصة", "خيار المعالجة", "إجراء المعالجة", "المسؤول", "تاريخ الاستحقاق", "الحالة", "% الإنجاز", "تنبيه"]


def d_trt():
    D = lambda n: TODAY + pd.Timedelta(days=n)
    rows = [
        ("R-01", "نقل / إعادة تأمين", "إبرام اتفاقية فائض خسارة كوارث (Cat XL) وضبط حدود التجمع في 10 رمضان و6 أكتوبر", "إعادة التأمين", D(45), "قيد التنفيذ", 40),
        ("R-01", "تخفيف", "مسح هندسي للمنشآت الصناعية وفرض اشتراطات سلامة ضد السيول", "الاكتتاب", D(90), "لم تبدأ", 0),
        ("R-02", "تخفيف", "ربط مبالغ التأمين بمؤشر تضخم وتطبيق شرط النسبة وتحديث التقييمات سنوياً", "الاكتتاب", D(-10), "قيد التنفيذ", 60),
        ("R-03", "نقل / إعادة تأمين", "تنويع معيدي التأمين واشتراط حد أدنى للتصنيف (A-)", "إعادة التأمين", D(30), "قيد التنفيذ", 50),
        ("R-04", "تخفيف", "برنامج امتثال لتعليمات FRA مع جدول متابعة شهري", "الامتثال", D(20), "قيد التنفيذ", 70),
        ("R-05", "تخفيف", "مراجعة اكتوارية مستقلة للاحتياطيات الفنية", "الاكتواري", D(-20), "لم تبدأ", 0),
        ("R-06", "تخفيف", "سياسة تحوط وتوافق عملات الأصول والالتزامات", "المالية والاستثمار", D(60), "لم تبدأ", 0),
        ("R-09", "تخفيف", "اتفاقيات أسعار مع ورش وموردين معتمدين", "المطالبات", D(75), "قيد التنفيذ", 25),
        ("R-10", "تخفيف", "نظام تحليلي لكشف الاحتيال", "تقنية المعلومات", D(120), "لم تبدأ", 0),
        ("R-11", "تخفيف", "خطة استمرارية الأعمال واختبار التعافي من الكوارث التقنية", "تقنية المعلومات", D(100), "قيد التنفيذ", 35),
        ("R-13", "قبول", "قبول مستوى المنافسة الحالي مع مراقبة الحصة السوقية ربع سنوياً", "الرئيس التنفيذي", D(-30), "مكتملة", 100),
        ("R-14", "تجنب", "وقف الاكتتاب في الأنشطة عالية التركز بدون إعادة تأمين", "الاكتتاب", D(-5), "مكتملة", 100),
        ("R-17", "استغلال الفرصة", "إطلاق منصة رقمية لإصدار الوثائق والمطالبات", "تقنية المعلومات", D(180), "قيد التنفيذ", 30),
        ("R-18", "استغلال الفرصة", "حزمة منتجات للمنشآت الصناعية والمدن الجديدة", "الاكتتاب", D(150), "لم تبدأ", 0),
    ]
    df = pd.DataFrame(rows, columns=["المعرّف", "خيار المعالجة", "إجراء المعالجة", "المسؤول", "تاريخ الاستحقاق", "الحالة", "% الإنجاز"])
    return df


def compute_trt(df):
    df = df.reset_index(drop=True).copy()
    for c in TR_COLS:
        if c not in df.columns:
            df[c] = None
    names = reg_names()
    df["المعرّف"] = df["المعرّف"].fillna("").astype(str)
    df["الخطر / الفرصة"] = df["المعرّف"].map(names).fillna("— اختر معرّفاً صحيحاً —")
    df["خيار المعالجة"] = df["خيار المعالجة"].where(df["خيار المعالجة"].isin(TREAT_OPTS), "تخفيف")
    df["الحالة"] = df["الحالة"].where(df["الحالة"].isin(TREAT_STATUS), "لم تبدأ")
    for c in ["إجراء المعالجة", "المسؤول"]:
        df[c] = df[c].fillna("").astype(str)
    df["تاريخ الاستحقاق"] = pd.to_datetime(df["تاريخ الاستحقاق"], errors="coerce")
    pct = pd.to_numeric(df["% الإنجاز"], errors="coerce").fillna(0).clip(0, 100)
    pct = pct.where(df["الحالة"] != "مكتملة", 100)
    df["% الإنجاز"] = pct.astype(int)
    alerts = []
    for _, r in df.iterrows():
        due, st_ = r["تاريخ الاستحقاق"], r["الحالة"]
        if st_ == "مكتملة":
            alerts.append("✅ منجزة")
        elif pd.isna(due):
            alerts.append("— لا يوجد تاريخ")
        elif due < TODAY:
            alerts.append(f"⚠️ متأخرة {(TODAY - due).days} يوم")
        elif (due - TODAY).days <= 14:
            alerts.append("⏳ تستحق خلال 14 يوماً")
        else:
            alerts.append("🟢 ضمن الموعد")
    df["تنبيه"] = alerts
    return df[TR_COLS]


def raci_default(cat, name):
    plan = {
        "استراتيجية": ("الرئيس التنفيذي", ["مدير إدارة المخاطر"], ["لجنة المخاطر", "الاكتتاب"], ["مجلس الإدارة", "المراجعة الداخلية"]),
        "مالية": ("المالية والاستثمار", ["الاكتواري"], ["إعادة التأمين", "مدير إدارة المخاطر"], ["لجنة المخاطر", "مجلس الإدارة"]),
        "تشغيلية": ("الاكتتاب", ["المطالبات"], ["تقنية المعلومات", "مدير إدارة المخاطر"], ["المراجعة الداخلية", "لجنة المخاطر"]),
        "سمعة": ("الرئيس التنفيذي", ["المطالبات"], ["الامتثال"], ["مجلس الإدارة"]),
        "امتثال": ("الامتثال", ["مدير إدارة المخاطر"], ["المراجعة الداخلية"], ["مجلس الإدارة", "لجنة المخاطر"]),
        "فرص": ("الرئيس التنفيذي", ["الاكتتاب", "تقنية المعلومات"], ["المالية والاستثمار"], ["لجنة المخاطر"]),
    }
    a, rs, cs, is_ = plan.get(cat, plan["تشغيلية"])
    if "إعادة التأمين" in name or "المعيدين" in name:
        a, rs = "إعادة التأمين", ["المالية والاستثمار"]
    if "الاكتوارية" in name:
        a = "الرئيس التنفيذي"
    vals = {r: "" for r in ROLES}
    for r in cs:
        vals[r] = "C"
    for r in is_:
        vals[r] = "I"
    for r in rs:
        vals[r] = "R"
    vals[a] = "A/R" if a in rs else "A"
    return vals


RACI_COLS = ["المعرّف", "الخطر / الفرصة"] + ROLES + ["التحقق"]


def compute_raci(df):
    reg = st.session_state.reg
    old = {r["المعرّف"]: r for _, r in df.iterrows()} if df is not None and len(df) else {}
    rows = []
    for _, r in reg.iterrows():
        o = old.get(r["المعرّف"])
        vals = {ro: (o[ro] if o is not None and ro in o and o[ro] in RACI_VALUES else "") for ro in ROLES} if o is not None \
            else raci_default(r["الفئة"], r["الخطر / الفرصة"])
        a = sum(1 for v in vals.values() if "A" in str(v))
        rr = sum(1 for v in vals.values() if "R" in str(v))
        chk = "❌ لا يوجد مالك (A)" if a == 0 else ("❌ أكثر من مالك (A)" if a > 1 else ("⚠️ لا يوجد منفذ (R)" if rr == 0 else "✅"))
        rows.append({"المعرّف": r["المعرّف"], "الخطر / الفرصة": r["الخطر / الفرصة"], **vals, "التحقق": chk})
    return pd.DataFrame(rows, columns=RACI_COLS)


MON_COLS = ["المعرّف", "الخطر / الفرصة", "المستوى", "التكرار", "آخر مراجعة", "المراجعة التالية", "المتبقي (يوم)", "الحالة"]


def compute_mon(df):
    reg = st.session_state.reg
    old = {r["المعرّف"]: r for _, r in df.iterrows()} if df is not None and len(df) else {}
    demo = df is None or len(df) == 0
    rows = []
    for k, (_, r) in enumerate(reg.iterrows()):
        o = old.get(r["المعرّف"])
        if o is not None:
            freq = o["التكرار"] if o["التكرار"] in FREQ_DAYS else DEFAULT_FREQ[r["المستوى"]]
            last = pd.to_datetime(o["آخر مراجعة"], errors="coerce")
        else:
            freq = DEFAULT_FREQ[r["المستوى"]]
            last = TODAY - pd.Timedelta(days=(k * 17) % 110) if demo else TODAY
        if pd.isna(last):
            nxt, left, status = pd.NaT, None, "🔴 لم تُراجع قط"
        else:
            nxt = last + pd.Timedelta(days=FREQ_DAYS[freq])
            left = (nxt - TODAY).days
            status = f"🔴 متأخرة {-left} يوم" if left < 0 else ("🟠 مستحقة قريباً" if left <= 7 else "🟢 ضمن الجدول")
        rows.append({"المعرّف": r["المعرّف"], "الخطر / الفرصة": r["الخطر / الفرصة"], "المستوى": r["المستوى"],
                     "التكرار": freq, "آخر مراجعة": last, "المراجعة التالية": nxt, "المتبقي (يوم)": left, "الحالة": status})
    out = pd.DataFrame(rows, columns=MON_COLS)
    out["آخر مراجعة"] = pd.to_datetime(out["آخر مراجعة"])
    out["المراجعة التالية"] = pd.to_datetime(out["المراجعة التالية"])
    return out


COM_FREQ = FREQS + ["عند الحدوث"]
COM_COLS = ["التقرير / الاتصال", "الجمهور", "المرجع", "التكرار", "المسؤول", "الوسيلة", "آخر إصدار", "الإصدار القادم", "الحالة"]


def d_com():
    D = lambda n: TODAY - pd.Timedelta(days=n)
    rows = [
        ("تقرير المخاطر الشهري للإدارة العليا", "الإدارة التنفيذية", "6.7", "شهرية", "مدير إدارة المخاطر", "تقرير + اجتماع", D(20)),
        ("تقرير لجنة المخاطر", "لجنة المخاطر", "6.7", "ربع سنوية", "مدير إدارة المخاطر", "اجتماع + محضر", D(60)),
        ("تقرير المخاطر لمجلس الإدارة", "مجلس الإدارة", "6.7", "ربع سنوية", "رئيس لجنة المخاطر", "تقرير مجلس", D(110)),
        ("تقرير الملاءة والاحتياطيات للهيئة العامة للرقابة المالية", "الهيئة العامة للرقابة المالية FRA", "6.7", "ربع سنوية", "الامتثال", "نماذج الهيئة", D(75)),
        ("تقرير تجميع الكوارث لمعيدي التأمين", "معيدو التأمين", "6.2", "نصف سنوية", "إعادة التأمين", "بريد رسمي", D(150)),
        ("تنبيه فوري بالأحداث الجسيمة", "الإدارة العليا", "6.7", "عند الحدوث", "مدير إدارة المخاطر", "بريد + اتصال", D(40)),
        ("نشرة التوعية بالمخاطر", "جميع الموظفين", "6.2", "ربع سنوية", "مدير إدارة المخاطر", "بريد داخلي", D(95)),
        ("ورش عمل تقييم المخاطر مع وحدات الأعمال", "مديرو الإدارات", "6.2", "نصف سنوية", "مدير إدارة المخاطر", "ورشة عمل", D(100)),
    ]
    return compute_com(pd.DataFrame(rows, columns=["التقرير / الاتصال", "الجمهور", "المرجع", "التكرار", "المسؤول", "الوسيلة", "آخر إصدار"]))


def compute_com(df):
    df = df.reset_index(drop=True).copy()
    for c in COM_COLS:
        if c not in df.columns:
            df[c] = None
    for c in ["التقرير / الاتصال", "الجمهور", "المرجع", "المسؤول", "الوسيلة"]:
        df[c] = df[c].fillna("").astype(str)
    df["التكرار"] = df["التكرار"].where(df["التكرار"].isin(COM_FREQ), "ربع سنوية")
    df["آخر إصدار"] = pd.to_datetime(df["آخر إصدار"], errors="coerce")
    nxt, stat = [], []
    for _, r in df.iterrows():
        days = FREQ_DAYS.get(r["التكرار"])
        if days is None:
            nxt.append(pd.NaT); stat.append("— عند الحاجة")
        elif pd.isna(r["آخر إصدار"]):
            nxt.append(pd.NaT); stat.append("🔴 لم يصدر")
        else:
            n = r["آخر إصدار"] + pd.Timedelta(days=days)
            left = (n - TODAY).days
            nxt.append(n)
            stat.append(f"🔴 متأخر {-left} يوم" if left < 0 else ("🟠 يستحق قريباً" if left <= 7 else "🟢 ضمن الجدول"))
    df["الإصدار القادم"] = pd.to_datetime(pd.Series(nxt, index=df.index))
    df["الحالة"] = stat
    return df[COM_COLS]


MAT_DIMS = ["القيادة", "التكامل", "المنهجية", "المعالجة", "المراقبة والإبلاغ"]
MAT_LEVELS = {1: "أولي", 2: "متكرر", 3: "معرَّف", 4: "مُدار", 5: "مُحسَّن"}


def d_mat():
    q = [
        ("القيادة", "التزام مجلس الإدارة والإدارة العليا بسياسة إدارة المخاطر", 4),
        ("القيادة", "تخصيص الموارد والصلاحيات لوظيفة المخاطر", 3),
        ("القيادة", "وضوح واعتماد شهية المخاطر وحدود التحمل", 3),
        ("التكامل", "دمج المخاطر في التخطيط الاستراتيجي وقياس الأداء", 2),
        ("التكامل", "دمج المخاطر في عمليات الاكتتاب والمطالبات", 3),
        ("التكامل", "الثقافة المؤسسية والتوعية بالمخاطر", 2),
        ("المنهجية", "اعتماد منهجية موثقة وفق ISO 31000", 4),
        ("المنهجية", "معايير ومصفوفة مخاطر معتمدة", 4),
        ("المنهجية", "جودة تحديد وتحليل المخاطر (النماذج الاكتوارية ونماذج الكوارث)", 3),
        ("المعالجة", "وجود خطط معالجة بمسؤول وموعد محدد", 3),
        ("المعالجة", "فاعلية الضوابط وبرنامج إعادة التأمين", 4),
        ("المعالجة", "تقييم المخاطر المتبقية بعد المعالجة", 2),
        ("المراقبة والإبلاغ", "انتظام المراجعات الدورية للسجل", 2),
        ("المراقبة والإبلاغ", "مؤشرات المخاطر الرئيسية KRIs", 2),
        ("المراقبة والإبلاغ", "جودة التقارير للإدارة العليا والجهات الرقابية", 3),
    ]
    return pd.DataFrame(q, columns=["البعد", "المعيار", "الدرجة"])


def d_mat_w():
    return pd.DataFrame({"البعد": MAT_DIMS, "الوزن %": [20.0] * 5})


SHEETS = [("الإطار المؤسسي", "fw"), ("السياق الخارجي", "ctx_ext"), ("السياق الداخلي", "ctx_int"), ("معايير المخاطر", "crit"),
          ("مقياس الاحتمالية", "scale_l"), ("مقياس الأثر", "scale_i"), ("حدود الاحتفاظ", "retention"),
          ("سجل المخاطر", "reg"), ("خطط المعالجة", "trt"), ("RACI", "raci"), ("المراجعات", "mon"),
          ("سجل الإبلاغ", "com"), ("النضج", "mat"), ("أوزان النضج", "mat_w")]
PERSIST = [k for _, k in SHEETS] + ["thr", "company"]


def init_state():
    ss = st.session_state
    if ss.get("_init"):
        return
    ss.page = "home"
    ss.company = "شركة تأمين ممتلكات مصرية"
    ss.thr = {"med": 6, "high": 13}
    ss.fw, ss.ctx_ext, ss.ctx_int = d_fw(), d_ctx_ext(), d_ctx_int()
    ss.crit, ss.scale_l, ss.scale_i, ss.retention = d_crit(), d_scale_l(), d_scale_i(), d_retention()
    ss.reg = d_reg()
    ss.trt = compute_trt(d_trt())
    ss.raci = compute_raci(None)
    ss.mon = compute_mon(None)
    ss.com = d_com()
    ss.mat, ss.mat_w = d_mat(), d_mat_w()
    ss._init = True


init_state()
ss = st.session_state


# ───────────────────────── المؤشرات والرسوم ─────────────────────────
def mat_scores():
    m = ss.mat.copy()
    m["الدرجة"] = pd.to_numeric(m["الدرجة"], errors="coerce").fillna(1).clip(1, 5)
    dim = m.groupby("البعد")["الدرجة"].mean().reindex(MAT_DIMS).fillna(1)
    w = ss.mat_w.set_index("البعد")["الوزن %"].reindex(MAT_DIMS)
    w = pd.to_numeric(w, errors="coerce").fillna(0)
    overall = float((dim * w).sum() / w.sum()) if w.sum() > 0 else float(dim.mean())
    return dim, overall


def get_kpis():
    reg, trt, mon, fw = ss.reg, compute_trt(ss.trt), ss.mon, ss.fw
    threats = reg[reg["النوع"] == "تهديد"]
    fw_pct = (fw["الحالة"].eq("مكتمل").sum() + 0.5 * fw["الحالة"].eq("قيد التطبيق").sum()) / max(len(fw), 1)
    trt_pct = trt["% الإنجاز"].mean() / 100 if len(trt) else 0
    mon_overdue = int(mon["الحالة"].str.startswith("🔴").sum())
    mon_pct = 1 - mon_overdue / max(len(mon), 1)
    _, mat = mat_scores()
    index = 100 * (0.25 * mat / 5 + 0.25 * fw_pct + 0.25 * trt_pct + 0.25 * mon_pct)
    return dict(
        total=len(reg), threats=len(threats), opps=int((reg["النوع"] == "فرصة").sum()),
        high=int((threats["المستوى"] == "مرتفع").sum()), avg=float(threats["درجة الخطر"].mean()) if len(threats) else 0,
        trt_pct=trt_pct, trt_overdue=int(trt["تنبيه"].str.startswith("⚠️").sum()), mon_overdue=mon_overdue,
        mat=mat, fw_pct=fw_pct, mon_pct=mon_pct, index=index,
    )


def heatmap(reg, typ="تهديد", key="hm"):
    sub = reg[reg["النوع"] == typ]
    xl = ["1 ضئيل", "2 طفيف", "3 متوسط", "4 كبير", "5 كارثي"]
    yl = ["5 شبه مؤكد", "4 مرجح", "3 محتمل", "2 غير محتمل", "1 نادر"]
    z, txt, hov = [], [], []
    for l in range(5, 0, -1):
        rz, rt, rh = [], [], []
        for i in range(1, 6):
            s = l * i
            ids = sub[(sub["الاحتمالية"] == l) & (sub["الأثر"] == i)]["المعرّف"].tolist()
            rz.append(zone_of(s))
            rt.append(("<br>".join(ids) if len(ids) <= 3 else f"{len(ids)} عناصر") if ids else f"<span style='color:#777'>{s}</span>")
            rh.append(f"الاحتمالية {l} × الأثر {i} = {s}<br>" + (", ".join(ids) if ids else "—"))
        z.append(rz); txt.append(rt); hov.append(rh)
    scale = ([[0, "#8fd19e"], [0.333, "#8fd19e"], [0.333, "#ffe08a"], [0.667, "#ffe08a"], [0.667, "#f28b82"], [1, "#f28b82"]]
             if typ == "تهديد" else
             [[0, "#cfe8fc"], [0.333, "#cfe8fc"], [0.333, "#8cc4f0"], [0.667, "#8cc4f0"], [0.667, "#3f8fd8"], [1, "#3f8fd8"]])
    fig = go.Figure(go.Heatmap(z=z, x=xl, y=yl, text=txt, texttemplate="%{text}", hovertext=hov, hoverinfo="text",
                               colorscale=scale, zmin=0, zmax=2, showscale=False, xgap=3, ygap=3))
    fig.update_yaxes(autorange="reversed", title="الاحتمالية")
    fig.update_xaxes(title="الأثر", side="bottom")
    fig.update_layout(height=430, title=f"مصفوفة {typ}ات 5×5" if typ == "تهديد" else "مصفوفة الفرص 5×5")
    plot(fig, key)


# ───────────────────────── الشريط الرئيسي والتنقل ─────────────────────────
def go_to(p):
    ss.page = p


st.markdown(
    f"<div class='hero'><h1>🛡️ GRC MIND — إدارة المخاطر المؤسسية</h1>"
    f"<p>{ss.company} &nbsp;|&nbsp; متوافق مع ISO 31000:2018 &nbsp;|&nbsp; تاريخ اليوم: {TODAY.strftime('%Y-%m-%d')}</p></div>",
    unsafe_allow_html=True,
)
for chunk in (PAGES[:6], PAGES[6:]):
    cols = st.columns(len(chunk))
    for col, (pid, label) in zip(cols, chunk):
        col.button(label, key=f"nav_{pid}", on_click=go_to, args=(pid,),
                   type="primary" if ss.page == pid else "secondary")
st.divider()

# ───────────────────────── الشريط الجانبي ─────────────────────────
with st.sidebar:
    st.header("⚙️ الإعدادات")
    ss.company = st.text_input("اسم الشركة", ss.company)
    if st.button("💾 حفظ البيانات محلياً"):
        with open(SAVE_FILE, "wb") as f:
            pickle.dump({k: ss[k] for k in PERSIST}, f)
        st.success("تم الحفظ")
    if st.button("📂 تحميل آخر حفظ"):
        if os.path.exists(SAVE_FILE):
            with open(SAVE_FILE, "rb") as f:
                for k, v in pickle.load(f).items():
                    ss[k] = v
            for k in [k for k in ss.keys() if k.endswith("_v")]:
                ss[k] += 1
            st.rerun()
        else:
            st.warning("لا يوجد ملف محفوظ")
    try:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as xw:
            for sheet, k in SHEETS:
                ss[k].to_excel(xw, sheet_name=sheet, index=False)
        st.download_button("📥 تصدير كل الجداول Excel", buf.getvalue(), "GRC_MIND_ERM.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as e:  # noqa
        st.caption(f"تعذر التصدير: {e}")
    if st.button("♻️ إعادة ضبط البيانات التجريبية"):
        for k in list(ss.keys()):
            del ss[k]
        st.rerun()

page = ss.page

# ───────────────────────── 0) الغلاف ─────────────────────────
if page == "home":
    k = get_kpis()
    c = st.columns(5)
    c[0].metric("إجمالي السجل", k["total"])
    c[1].metric("مخاطر مرتفعة", k["high"])
    c[2].metric("فرص", k["opps"])
    c[3].metric("نضج الإطار (من 5)", f"{k['mat']:.2f}")
    c[4].metric("مؤشر الجاهزية المؤسسية", f"{k['index']:.0f}%")
    st.markdown("### أقسام الأداة")
    cards = [
        ("5 | تقييم الإطار المؤسسي", "12 عنصراً من ISO 31000 مع حالة التطبيق وملاحظات تنفيذية."),
        ("6.3.3 | السياق", "6 عوامل خارجية و10 عوامل داخلية لشركة تأمين الممتلكات."),
        ("6.3.4 | معايير المخاطر", "7 بنود للاعتماد: مصفوفة 5×5، مستويات القبول، حدود الاحتفاظ."),
        ("6.4 | سجل المخاطر", "6 فئات، تمييز التهديد/الفرصة، وحساب تلقائي للمستوى."),
        ("6.5 | المعالجة", "خيارات المعالجة مع المسؤول والاستحقاق وكشف التأخير."),
        ("5.4.3 | RACI", "مصفوفة مسؤوليات مع تحقق آلي من وجود مالك واحد لكل خطر."),
        ("6.6 | المراقبة", "جدولة تلقائية للمراجعات وتنبيهات التأخير."),
        ("6.2/6.7 | الإبلاغ", "سجل التقارير للإدارة العليا والمجلس واللجان والهيئة."),
        ("النضج المؤسسي", "5 أبعاد و15 معياراً وحساب الدرجة الإجمالية من 5."),
        ("لوحة التحكم", "مؤشرات أداء ورسوم تفاعلية ومؤشر جاهزية مركب."),
    ]
    for r in range(0, len(cards), 5):
        cols = st.columns(5)
        for col, (t, d) in zip(cols, cards[r:r + 5]):
            col.markdown(f"<div class='card'><h4>{t}</h4><p>{d}</p></div>", unsafe_allow_html=True)
    st.info("ابدأ من قسم **الإطار المؤسسي**، ثم **السياق**، ثم اعتمد **معايير المخاطر** قبل تعبئة سجل المخاطر. "
            "كل الجداول قابلة للتعديل مباشرة، ويمكن إضافة/حذف الصفوف في الجداول الديناميكية.")

# ───────────────────────── 1) الإطار المؤسسي ─────────────────────────
elif page == "fw":
    section("تقييم الإطار المؤسسي", "Clause 5 — Framework", "حدّث حالة تطبيق كل عنصر وأضف الملاحظات التنفيذية.")
    fw = ss.fw
    done = (fw["الحالة"] == "مكتمل").sum()
    prog = (fw["الحالة"] == "قيد التطبيق").sum()
    c = st.columns(4)
    c[0].metric("مكتمل", int(done)); c[1].metric("قيد التطبيق", int(prog))
    c[2].metric("غير مطبق", int((fw["الحالة"] == "غير مطبق").sum()))
    c[3].metric("نسبة الاكتمال", f"{(done + 0.5 * prog) / len(fw):.0%}")
    table("fw", disabled=["البند", "المحور", "المتطلب"], config={
        "الحالة": st.column_config.SelectboxColumn(options=IMPL, required=True),
        "المتطلب": st.column_config.TextColumn(width="large"),
        "ملاحظات تنفيذية": st.column_config.TextColumn(width="large"),
    })
    by = fw.groupby("المحور")["الحالة"].apply(lambda s: (s.eq("مكتمل").sum() + 0.5 * s.eq("قيد التطبيق").sum()) / len(s) * 100)
    fig = go.Figure(go.Bar(x=by.values, y=by.index, orientation="h", marker_color="#145c7a", text=[f"{v:.0f}%" for v in by.values]))
    fig.update_layout(title="نسبة اكتمال كل محور", xaxis=dict(range=[0, 100]), height=320, yaxis=dict(autorange="reversed"))
    plot(fig, "fw_chart")

# ───────────────────────── 2) السياق ─────────────────────────
elif page == "ctx":
    section("السياق الخارجي والداخلي", "Clause 6.3.3 — Context", "حدد العوامل المؤثرة وطبيعة أثرها ودرجتها (1–5).")
    cfg = {
        "طبيعة الأثر": st.column_config.SelectboxColumn(options=["تهديد", "فرصة", "محايد"], required=True),
        "درجة التأثير": st.column_config.NumberColumn(min_value=1, max_value=5, step=1),
        "الوصف والأثر على الشركة": st.column_config.TextColumn(width="large"),
    }
    t1, t2 = st.tabs(["🌍 العوامل الخارجية (6)", "🏢 العوامل الداخلية (10)"])
    with t1:
        table("ctx_ext", dynamic=True, config=cfg)
    with t2:
        table("ctx_int", dynamic=True, config=cfg)

# ───────────────────────── 3) معايير المخاطر ─────────────────────────
elif page == "crit":
    section("معايير المخاطر الرسمية", "Clause 6.3.4 — Risk Criteria", "اعتمد البنود السبعة قبل بدء التقييم.")
    ok = int(ss.crit["معتمد"].sum())
    (st.success if ok == len(ss.crit) else st.warning)(f"البنود المعتمدة: {ok} من {len(ss.crit)} — "
                                                      + ("المعايير جاهزة للتقييم ✅" if ok == len(ss.crit) else "لا تبدأ التقييم قبل اعتماد كل البنود"))
    table("crit", disabled=["م", "البند", "المرجع"], config={
        "معتمد": st.column_config.CheckboxColumn("معتمد"),
        "المعيار المعتمد": st.column_config.TextColumn(width="large"),
    })
    st.markdown("#### 1) مصفوفة 5×5 وحدود المستويات (4)")
    c1, c2, c3 = st.columns([1, 1, 2])
    med = c1.number_input("بداية المستوى المتوسط (≥)", 2, 24, ss.thr["med"])
    high = c2.number_input("بداية المستوى المرتفع (≥)", 3, 25, ss.thr["high"])
    if high <= med:
        c3.error("يجب أن يكون حد المرتفع أكبر من حد المتوسط")
    else:
        ss.thr = {"med": int(med), "high": int(high)}
        ss.reg = compute_register(ss.reg)
        ss.mon = compute_mon(ss.mon)
    m, h = thresholds()
    acc = pd.DataFrame([
        ("منخفض", f"1 – {m - 1}", "قبول مع مراقبة روتينية ضمن المراجعة السنوية"),
        ("متوسط", f"{m} – {h - 1}", "خطة معالجة خلال 6 أشهر وموافقة مدير الإدارة"),
        ("مرتفع", f"{h} – 25", "معالجة فورية وتصعيد للجنة المخاطر ومجلس الإدارة"),
    ], columns=["المستوى", "درجة الخطر", "معيار القبول والإجراء"])
    cc = st.columns([1, 1])
    with cc[0]:
        heatmap(ss.reg, "تهديد", "crit_hm")
    with cc[1]:
        st.markdown("**مستويات القبول**")
        show_df(acc, "المستوى")
    st.markdown("#### 2) مقياس الاحتمالية  |  3) مقياس الأثر")
    a, b = st.columns(2)
    with a:
        table("scale_l", disabled=["الدرجة"])
    with b:
        table("scale_i", disabled=["الدرجة"])
    st.markdown("#### 5) حدود الاحتفاظ الصافي")
    table("retention", dynamic=True, config={
        "الاحتفاظ لكل خطر (مليون ج.م)": st.column_config.NumberColumn(min_value=0.0, format="%.1f"),
        "الاحتفاظ لكل حدث (مليون ج.م)": st.column_config.NumberColumn(min_value=0.0, format="%.1f"),
    })
    st.caption("القيم الواردة استرشادية ويجب اعتمادها من لجنة المخاطر ومجلس الإدارة بما يتفق مع حقوق الملكية واتفاقيات إعادة التأمين.")

# ───────────────────────── 4) سجل المخاطر ─────────────────────────
elif page == "reg":
    section("سجل المخاطر المؤسسي الشامل", "Clause 6.4 — Risk Register",
            "أضف صفوفاً جديدة من أسفل الجدول؛ تُحسب الدرجة والمستوى تلقائياً (الاحتمالية × الأثر).")
    ss.reg = compute_register(ss.reg)
    reg = ss.reg
    c = st.columns(5)
    c[0].metric("إجمالي", len(reg))
    c[1].metric("تهديدات", int((reg["النوع"] == "تهديد").sum()))
    c[2].metric("فرص", int((reg["النوع"] == "فرصة").sum()))
    c[3].metric("مرتفع", int((reg["المستوى"] == "مرتفع").sum()))
    c[4].metric("متوسط", int((reg["المستوى"] == "متوسط").sum()))
    f1, f2 = st.columns(2)
    fc = f1.multiselect("عرض ملوّن: فلترة حسب الفئة", CATS, default=CATS)
    ft = f2.multiselect("فلترة حسب النوع", TYPES, default=TYPES)
    table("reg", post=compute_register, dynamic=True, disabled=["المعرّف", "درجة الخطر", "المستوى"], config={
        "الفئة": st.column_config.SelectboxColumn(options=CATS, required=True),
        "النوع": st.column_config.SelectboxColumn(options=TYPES, required=True),
        "الاحتمالية": st.column_config.NumberColumn(min_value=1, max_value=5, step=1),
        "الأثر": st.column_config.NumberColumn(min_value=1, max_value=5, step=1),
        "الوصف": st.column_config.TextColumn(width="large"),
        "الخطر / الفرصة": st.column_config.TextColumn(width="large"),
    }, height=520)
    st.caption("ملاحظة: اختيار النوع «فرصة» يضبط الفئة تلقائياً على «فرص» والعكس صحيح.")
    with st.expander("🎨 عرض ملوّن للسجل (للقراءة فقط)", expanded=True):
        view = reg[reg["الفئة"].isin(fc) & reg["النوع"].isin(ft)].sort_values("درجة الخطر", ascending=False)
        show_df(view, "المستوى")
    m1, m2 = st.columns(2)
    with m1:
        heatmap(reg, "تهديد", "reg_hm_t")
    with m2:
        heatmap(reg, "فرصة", "reg_hm_o")

# ───────────────────────── 5) المعالجة ─────────────────────────
elif page == "trt":
    section("خطط المعالجة والخيارات الرسمية", "Clause 6.5 — Risk Treatment",
            "اربط كل إجراء بخطر من السجل وبمسؤول وتاريخ استحقاق؛ يظهر التأخير تلقائياً.")
    ss.trt = compute_trt(ss.trt)
    trt = ss.trt
    c = st.columns(4)
    c[0].metric("إجمالي الإجراءات", len(trt))
    c[1].metric("مكتملة", int((trt["الحالة"] == "مكتملة").sum()))
    c[2].metric("قيد التنفيذ", int((trt["الحالة"] == "قيد التنفيذ").sum()))
    c[3].metric("متأخرة ⚠️", int(trt["تنبيه"].str.startswith("⚠️").sum()))
    over = trt[trt["تنبيه"].str.startswith("⚠️")]
    if len(over):
        st.error("إجراءات معالجة متأخرة: " + "، ".join(f"{r['المعرّف']} ({r['تنبيه'].replace('⚠️ ', '')})" for _, r in over.iterrows()))
    no_plan = set(ss.reg[(ss.reg["المستوى"] == "مرتفع") & (ss.reg["النوع"] == "تهديد")]["المعرّف"]) - set(trt["المعرّف"])
    if no_plan:
        st.warning("مخاطر مرتفعة بلا خطة معالجة: " + "، ".join(sorted(no_plan)))
    table("trt", post=compute_trt, dynamic=True, disabled=["الخطر / الفرصة", "تنبيه"], config={
        "المعرّف": st.column_config.SelectboxColumn(options=list(ss.reg["المعرّف"]), required=True),
        "خيار المعالجة": st.column_config.SelectboxColumn(options=TREAT_OPTS, required=True),
        "الحالة": st.column_config.SelectboxColumn(options=TREAT_STATUS, required=True),
        "تاريخ الاستحقاق": st.column_config.DateColumn(format="YYYY-MM-DD"),
        "% الإنجاز": st.column_config.NumberColumn(min_value=0, max_value=100, step=5),
        "إجراء المعالجة": st.column_config.TextColumn(width="large"),
    }, height=480)
    cnt = trt["خيار المعالجة"].value_counts()
    fig = go.Figure(go.Bar(x=cnt.index, y=cnt.values, marker_color="#145c7a"))
    fig.update_layout(title="توزيع خيارات المعالجة", height=300)
    plot(fig, "trt_opts")

# ───────────────────────── 6) RACI ─────────────────────────
elif page == "raci":
    section("مصفوفة المسؤوليات RACI", "Clause 5.4.3 — Roles & Responsibilities",
            "A = المالك المساءل (واحد فقط) | R = المنفذ | C = المستشار | I = المُبلَّغ | A/R = مالك ومنفذ.")
    ss.raci = compute_raci(ss.raci)
    bad = ss.raci[~ss.raci["التحقق"].str.startswith("✅")]
    if len(bad):
        st.warning("يلزم تصحيح: " + "، ".join(f"{r['المعرّف']} ({r['التحقق'][2:]})" for _, r in bad.iterrows()))
    else:
        st.success("كل خطر له مالك واحد (A) ومنفذ (R) ✅")
    table("raci", post=compute_raci, disabled=["المعرّف", "الخطر / الفرصة", "التحقق"],
          config={r: st.column_config.SelectboxColumn(options=RACI_VALUES, width="small") for r in ROLES}, height=520)

# ───────────────────────── 7) المراقبة ─────────────────────────
elif page == "mon":
    section("المراقبة والمراجعة الدورية وكشف التأخير", "Clause 6.6 — Monitoring & Review",
            "المراجعة التالية = آخر مراجعة + دورية التكرار. التكرار الافتراضي: مرتفع شهرياً، متوسط ربع سنوي، منخفض سنوياً.")
    ss.mon = compute_mon(ss.mon)
    mon = ss.mon
    late = mon[mon["الحالة"].str.startswith("🔴")]
    soon = mon[mon["الحالة"].str.startswith("🟠")]
    c = st.columns(3)
    c[0].metric("ضمن الجدول", int(mon["الحالة"].str.startswith("🟢").sum()))
    c[1].metric("مستحقة قريباً (≤7 أيام)", len(soon))
    c[2].metric("متأخرة 🔴", len(late))
    if len(late):
        st.error(f"🚨 تنبيه تأخير: {len(late)} سجلات لم تُحدَّث في موعدها — " + "، ".join(late["المعرّف"]))
    a, b = st.columns([3, 1])
    pick = a.multiselect("تسجيل مراجعة اليوم للسجلات المحددة", list(mon["المعرّف"]), default=list(late["المعرّف"]))
    if b.button("✔️ تسجيل مراجعة اليوم", disabled=not pick):
        m2 = ss.mon.copy()
        m2.loc[m2["المعرّف"].isin(pick), "آخر مراجعة"] = TODAY
        ss.mon = compute_mon(m2)
        ss.mon_v += 1
        st.rerun()
    table("mon", post=compute_mon, disabled=["المعرّف", "الخطر / الفرصة", "المستوى", "المراجعة التالية", "المتبقي (يوم)", "الحالة"], config={
        "التكرار": st.column_config.SelectboxColumn(options=FREQS, required=True),
        "آخر مراجعة": st.column_config.DateColumn(format="YYYY-MM-DD"),
        "المراجعة التالية": st.column_config.DateColumn(format="YYYY-MM-DD"),
    }, height=520)

# ───────────────────────── 8) الإبلاغ ─────────────────────────
elif page == "com":
    section("سجل التواصل والإبلاغ", "Clause 6.2 & 6.7 — Communication & Reporting",
            "تقارير الإدارة العليا ومجلس الإدارة ولجان المخاطر والجهات الرقابية، مع جدولة الإصدار القادم.")
    ss.com = compute_com(ss.com)
    late = ss.com[ss.com["الحالة"].str.startswith("🔴")]
    if len(late):
        st.error("تقارير متأخرة: " + "، ".join(late["التقرير / الاتصال"]))
    table("com", post=compute_com, dynamic=True, disabled=["الإصدار القادم", "الحالة"], config={
        "التكرار": st.column_config.SelectboxColumn(options=COM_FREQ, required=True),
        "المرجع": st.column_config.SelectboxColumn(options=["6.2", "6.7"], required=True),
        "آخر إصدار": st.column_config.DateColumn(format="YYYY-MM-DD"),
        "الإصدار القادم": st.column_config.DateColumn(format="YYYY-MM-DD"),
        "التقرير / الاتصال": st.column_config.TextColumn(width="large"),
    }, height=400)

# ───────────────────────── 9) النضج ─────────────────────────
elif page == "mat":
    section("نموذج النضج المؤسسي", "Maturity Model — 5 Dimensions",
            "قيّم كل معيار من 1 إلى 5. 1 أولي، 2 متكرر، 3 معرَّف، 4 مُدار، 5 مُحسَّن.")
    st.markdown("**أوزان الأبعاد %** (الافتراضي متساوٍ 20% لكل بعد؛ تُطبَّع تلقائياً إذا لم يكن المجموع 100)")
    table("mat_w", disabled=["البعد"], config={"الوزن %": st.column_config.NumberColumn(min_value=0.0, max_value=100.0, step=5.0)})
    st.markdown("**معايير التقييم**")
    table("mat", disabled=["البعد", "المعيار"], config={
        "الدرجة": st.column_config.NumberColumn(min_value=1, max_value=5, step=1),
        "المعيار": st.column_config.TextColumn(width="large"),
    })
    dim, overall = mat_scores()
    c = st.columns(6)
    for col, d in zip(c, MAT_DIMS):
        col.metric(d, f"{dim[d]:.2f}")
    c[5].metric("الدرجة الإجمالية", f"{overall:.2f} / 5")
    st.info(f"المستوى العام: **{MAT_LEVELS[max(1, min(5, round(overall)))]}** — الدرجة {overall:.2f} من 5 ({overall / 5:.0%}).")
    fig = go.Figure(go.Scatterpolar(r=list(dim.values) + [dim.values[0]], theta=MAT_DIMS + [MAT_DIMS[0]], fill="toself",
                                    line_color="#145c7a", name="الحالي"))
    fig.add_trace(go.Scatterpolar(r=[4] * 6, theta=MAT_DIMS + [MAT_DIMS[0]], line=dict(color="#2e9e5b", dash="dash"), name="المستهدف (4)"))
    fig.update_layout(polar=dict(radialaxis=dict(range=[0, 5], tickvals=[1, 2, 3, 4, 5])), height=420, title="مخطط النضج")
    plot(fig, "mat_radar")

# ───────────────────────── 10) لوحة التحكم ─────────────────────────
elif page == "dash":
    section("لوحة التحكم التنفيذية", "Executive Dashboard", "نظرة شاملة على المخاطر والمعالجة والمراقبة والنضج.")
    ss.reg = compute_register(ss.reg)
    ss.mon = compute_mon(ss.mon)
    k = get_kpis()
    reg = ss.reg
    trt = compute_trt(ss.trt)
    if k["mon_overdue"] or k["trt_overdue"]:
        st.error(f"🚨 تنبيهات: {k['mon_overdue']} مراجعة متأخرة، {k['trt_overdue']} إجراء معالجة متأخر.")
    r1 = st.columns(5)
    r1[0].metric("إجمالي السجل", k["total"])
    r1[1].metric("التهديدات", k["threats"])
    r1[2].metric("الفرص", k["opps"])
    r1[3].metric("مخاطر مرتفعة", k["high"])
    r1[4].metric("متوسط درجة التهديد", f"{k['avg']:.1f}")
    r2 = st.columns(5)
    r2[0].metric("اكتمال المعالجة", f"{k['trt_pct']:.0%}")
    r2[1].metric("معالجات متأخرة", k["trt_overdue"])
    r2[2].metric("مراجعات متأخرة", k["mon_overdue"])
    r2[3].metric("اكتمال الإطار", f"{k['fw_pct']:.0%}")
    r2[4].metric("النضج (من 5)", f"{k['mat']:.2f}")

    a, b = st.columns(2)
    with a:
        lv = reg.groupby(["المستوى", "النوع"]).size().reset_index(name="العدد")
        fig = go.Figure()
        for t, col in (("تهديد", "#d93025"), ("فرصة", "#3f8fd8")):
            s = lv[lv["النوع"] == t].set_index("المستوى")["العدد"].reindex(["مرتفع", "متوسط", "منخفض"]).fillna(0)
            fig.add_trace(go.Bar(name=t, x=s.index, y=s.values, marker_color=col))
        fig.update_layout(barmode="group", title="توزيع المستويات (مرتفع / متوسط / منخفض)", height=380)
        plot(fig, "d_levels")
    with b:
        heatmap(reg, "تهديد", "d_hm")
    c1, c2 = st.columns(2)
    with c1:
        cat = reg.groupby("الفئة").agg(عدد=("المعرّف", "count"), متوسط=("درجة الخطر", "mean")).reindex(CATS).dropna().reset_index()
        fig = go.Figure(go.Bar(x=cat["الفئة"], y=cat["عدد"], marker_color="#145c7a", name="العدد",
                               text=[f"متوسط {v:.1f}" for v in cat["متوسط"]]))
        fig.update_layout(title="المخاطر حسب الفئة", height=360)
        plot(fig, "d_cat")
    with c2:
        stc = trt["الحالة"].value_counts().reindex(TREAT_STATUS).fillna(0)
        fig = go.Figure(go.Pie(labels=stc.index, values=stc.values, hole=0.55,
                               marker_colors=["#b0bec5", "#f4b400", "#2e9e5b"]))
        fig.update_layout(title="حالة خطط المعالجة", height=360)
        plot(fig, "d_trt")
    d1, d2 = st.columns(2)
    with d1:
        top = reg[reg["النوع"] == "تهديد"].sort_values("درجة الخطر", ascending=False).head(10)
        fig = go.Figure(go.Bar(x=top["درجة الخطر"], y=top["المعرّف"] + " | " + top["الخطر / الفرصة"].str.slice(0, 38), orientation="h",
                               marker_color=[LEVEL_COLOR[v] for v in top["المستوى"]]))
        fig.update_layout(title="أعلى 10 تهديدات", height=430, yaxis=dict(autorange="reversed"))
        plot(fig, "d_top")
    with d2:
        fig = go.Figure(go.Indicator(
            mode="gauge+number", value=k["index"], number={"suffix": "%"},
            title={"text": "مؤشر الجاهزية المؤسسية (25% لكل ركن)"},
            gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#145c7a"},
                   "steps": [{"range": [0, 40], "color": "#f8d7da"}, {"range": [40, 70], "color": "#fff3cd"},
                             {"range": [70, 100], "color": "#d4edda"}]}))
        fig.update_layout(height=300)
        plot(fig, "d_gauge")
        st.caption("المؤشر = 25% نضج (من 5) + 25% اكتمال الإطار + 25% اكتمال المعالجة + 25% انتظام المراجعات.")
        dim, _ = mat_scores()
        fig = go.Figure(go.Scatterpolar(r=list(dim.values) + [dim.values[0]], theta=MAT_DIMS + [MAT_DIMS[0]], fill="toself", line_color="#145c7a"))
        fig.update_layout(polar=dict(radialaxis=dict(range=[0, 5])), height=300, title="أبعاد النضج")
        plot(fig, "d_radar")

st.markdown("<div style='text-align:center;color:#8a99a3;margin-top:24px;font-size:.85rem'>"
            "GRC MIND • ISO 31000:2018 • البيانات الواردة تجريبية وتحتاج اعتماداً قبل الاستخدام الرسمي</div>", unsafe_allow_html=True)
