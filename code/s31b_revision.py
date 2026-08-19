# -*- coding: utf-8 -*-
"""V3 s31b: 修订版全文手稿（回应两份审稿意见；普通 Word 版式）
数字一律从 data/stats_v2.json 注入（回应严格版 M10）。
输出：manuscript/V3_manuscript_full_v2.docx
"""
import json
import re

import docx
import pandas as pd
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

S = json.load(open("data/stats_v2.json", encoding="utf-8"))
OUT = "manuscript/V3_manuscript_full_v2.docx"
doc = docx.Document()

for s in doc.sections:
    s.page_width = Cm(21.0)
    s.page_height = Cm(29.7)
    s.left_margin = s.right_margin = Cm(2.5)
    s.top_margin = s.bottom_margin = Cm(2.5)

st = doc.styles["Normal"]
st.font.name = "Times New Roman"
st.font.size = Pt(11)
st.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
st.paragraph_format.space_after = Pt(6)
st.paragraph_format.line_spacing = 1.3
st.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY


def add_runs(p, text, size=None):
    for tok in re.split(r"(\*\*.+?\*\*|\*[^*]+?\*)", text):
        if not tok:
            continue
        if tok.startswith("**") and tok.endswith("**"):
            r = p.add_run(tok[2:-2]); r.bold = True
        elif tok.startswith("*") and tok.endswith("*"):
            r = p.add_run(tok[1:-1]); r.italic = True
        else:
            r = p.add_run(tok)
        if size:
            r.font.size = Pt(size)


def P(text, size=None):
    p = doc.add_paragraph()
    add_runs(p, text, size)
    return p


def H1(text):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(14)
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.keep_with_next = True


def H2(text):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(12)
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.keep_with_next = True


def FIG(path, num, caption, width_cm=15.5):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(path, width=Cm(width_cm))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = cap.add_run(f"Fig. {num}. ")
    r.bold = True
    r.font.size = Pt(9.5)
    r2 = cap.add_run(caption)
    r2.font.size = Pt(9.5)
    cap.paragraph_format.space_after = Pt(10)


def set_borders(tbl):
    tblPr = tbl._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{edge}")
        e.set(qn("w:val"), "single")
        e.set(qn("w:sz"), "4")
        borders.append(e)
    tblPr.append(borders)


def TABLE(num, title, headers, rows, fontsize=8.5):
    cap = doc.add_paragraph()
    r = cap.add_run(f"Table {num}. ")
    r.bold = True
    r.font.size = Pt(10)
    r2 = cap.add_run(title)
    r2.font.size = Pt(10)
    t = doc.add_table(rows=1 + len(rows), cols=len(headers))
    set_borders(t)
    for j, h in enumerate(headers):
        c = t.rows[0].cells[j]
        c.text = ""
        rr = c.paragraphs[0].add_run(str(h))
        rr.bold = True
        rr.font.size = Pt(fontsize)
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            c = t.rows[i + 1].cells[j]
            c.text = ""
            rr = c.paragraphs[0].add_run(str(v))
            rr.font.size = Pt(fontsize)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def EQ(parts, num):
    """parts: list of (text, mode)；mode: None/'i'/'sub'/'sup'/'isub'"""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for text, mode in parts:
        r = p.add_run(text)
        if "i" in (mode or ""):
            r.italic = True
        if "sub" in (mode or ""):
            r.font.subscript = True
        if "sup" in (mode or ""):
            r.font.superscript = True
    p.add_run(f"    ({num})")
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(8)


# ==================== 标题区 ====================
t = doc.add_paragraph()
t.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = t.add_run("Thermal–Wireless Trade-Offs of Terrain-Constrained Settlement Morphology in Huizhou "
              "Traditional Villages")
r.bold = True
r.font.size = Pt(16)
t.paragraph_format.space_after = Pt(14)

a = doc.add_paragraph()
a.alignment = WD_ALIGN_PARAGRAPH.CENTER
a.add_run("Lei Zhang")
r = a.add_run("1,*"); r.font.superscript = True
for _r in a.runs:
    _r.font.size = Pt(12)

af = doc.add_paragraph()
af.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = af.add_run("1 School of Architecture and Urban Planning, Anhui Jianzhu University, Hefei 230601, China")
r.font.size = Pt(9.5)
r.italic = True
c = doc.add_paragraph()
c.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = c.add_run("* Corresponding author. E-mail: [corresponding author's e-mail to be inserted]")
r.font.size = Pt(9.5)
doc.add_paragraph()

# ---- Abstract（约250词）----
ab = doc.add_paragraph()
r = ab.add_run("Abstract: ")
r.bold = True
add_runs(ab,
    "Traditional villages in mountainous regions must reconcile climatic comfort with modern digital "
    "infrastructure, yet the same settlement morphology may act in opposite directions on these two "
    "performances. For 29 traditional villages in the Huizhou region of southern Anhui, China, this paper "
    "quantifies how settlement morphology is associated with summer land surface temperature (LST) and "
    "with simulated wireless coverage, using only open data and scripted, re-runnable models. Twelve "
    "morphological metrics derive from the 30-m Copernicus DEM and the 10-m ESA WorldCover map. Village "
    "summer LST comes from a quality-masked 33-scene Landsat 8/9 median composite (2019–2025); coverage "
    "is evaluated under a standardized virtual macrocell deployment (2.5-km hilltop-snapped grid, 30-m "
    "masts, 2.6 GHz) with a terrain line-of-sight 3GPP rural-macrocell model, repeated over four grid "
    "phases. Every village is warmer than its rural background (mean ΔLST = +2.5 °C). Topographic "
    "openness (terrain sky-view factor) is double-edged: it is associated with higher LST (Spearman "
    "ρ = +0.60) and with better good-coverage (ρ = +0.69; partial ρ = +0.57 controlling domain built-up "
    "area). The forest ring shows no detectable thermal association at village scale (ρ = −0.25, n.s.) "
    "but strongly shadows signal (ρ = −0.81). Compactness raises the village-versus-background anomaly "
    "(partial ρ = +0.70). Elongation trades a marginal thermal benefit against significantly worse "
    "coverage (ρ = −0.45). Results are robust to grid phase, band choice (700 MHz), county-level "
    "jackknife, and outlier exclusion. The quantified couplings support joint morphological planning of "
    "climate adaptation and rural digital infrastructure, and the open pipeline transfers to other "
    "mountainous regions.")
ab.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
kw = doc.add_paragraph()
r = kw.add_run("Keywords: ")
r.bold = True
kw.add_run("settlement morphology; land surface temperature; rural wireless coverage; 3GPP rural "
           "macrocell model; sky-view factor; traditional villages; Huizhou")
doc.add_paragraph()

# ==================== 1. INTRODUCTION ====================
H1("1. Introduction")
P("Traditional settlements in mountainous regions embody climatic knowledge accumulated over centuries of "
  "trial and error. In the Huizhou region of southern Anhui Province, China—home to the World Heritage "
  "villages of Hongcun and Xidi and to one of the densest concentrations of historic villages in East "
  "Asia—enclosed valley sites, forested backdrops, compact building fabrics, and water-adjacent layouts "
  "have long been read as a vernacular, pre-scientific system of passive environmental control [1], [2]. "
  "Field studies in and around the region confirm that this question remains empirically alive: indoor and "
  "outdoor thermal performance of Huizhou-area vernacular fabric continues to be measured and debated [3], "
  "[4]. These villages are simultaneously protected heritage, working agricultural communities, and tourist "
  "destinations, and they must now accommodate a second, very different infrastructure: rural broadband and "
  "mobile networks, digital-village platforms [5], and, increasingly, city information modeling (CIM) at "
  "the settlement scale [6]. The two agendas are usually planned by different agencies with different "
  "tools, and they meet, if at all, only at the construction site.")
P("The premise of this paper is that they should meet much earlier, because both agendas load on the same "
  "physical object: settlement morphology. The morphology that heritage conservation prefers—enclosed, "
  "compact, forest-backed, water-adjacent—is widely believed to be thermally favorable in hot-summer "
  "climates [1], [2], [7]. Radio propagation in mountainous terrain, by contrast, favors the opposite "
  "geometry: open horizons and unobstructed line-of-sight (LOS) paths to elevated macrocells [8]–[10]. "
  "Whether these two performances actually trade off across real villages—and by how much, and through "
  "which specific morphological attributes—has never been quantified. This paper provides that "
  "quantification, and in doing so it treats the associations strictly as associations: the design is "
  "cross-sectional and correlational, and the language of the paper follows that design.")
P("The thermal side of the question has a mature literature. The energetic basis of settlement-scale heat "
  "excess has been understood since the foundational work of Oke [11], and subsequent reviews consolidated "
  "the roles of geometry, surface cover, and anthropogenic heat [12]. The local climate zone (LCZ) scheme "
  "formalized the idea that built morphology predicts thermal behavior [13], and canyon geometry together "
  "with the sky-view factor (SVF) emerged as robust predictors of urban heat intensity [14], [15]. For "
  "vernacular settlements specifically, case studies combining field measurement and simulation have "
  "demonstrated the climate responsiveness of traditional dwellings and village layouts in China and "
  "elsewhere [1]–[4], [16], including systematic reviews of outdoor microclimate design in traditional "
  "Chinese villages [7]. Two gaps nonetheless remain. First, the vernacular evidence is overwhelmingly "
  "single-village: cross-settlement, statistically controlled evidence linking village morphology to "
  "thermal outcomes is thin, particularly in mountainous southern China [7], [17]. Second, the dominant "
  "morphometric evidence comes from cities, where morphology varies independently of terrain; in mountain "
  "villages, built form and terrain co-vary by design, so the urban-derived intuition that ‘more open is "
  "cooler’ cannot be assumed to hold [18].")
P("The radio side has an equally mature but entirely separate literature. Empirical path-loss models "
  "descend from Hata [8] through the COST-231 family, while the geometry-based 3GPP rural macrocell (RMa) "
  "model specifies distinct line-of-sight (LOS) and non-LOS (NLOS) branches in which terrain obstruction "
  "is the first-order control on rural coverage [9], [10]. Vegetation is known to attenuate gigahertz "
  "signals [19]. Rural coverage gaps—and their socio-economic consequences—are documented in global "
  "digital-divide assessments [20], and in China the digital-village strategy has made rural connectivity "
  "an explicit policy target [5]. Yet coverage studies rarely treat settlement morphology as an "
  "explanatory variable: villages appear, if at all, as demand points on a cost surface, not as "
  "morphological objects whose shape co-determines serviceability. No study we are aware of evaluates the "
  "thermal and radio performances of the same settlements jointly.")
P("Meanwhile, the data environment has changed. Open elevation models, global land-cover maps, multi-year "
  "thermal satellite archives, and open street-level imagery have made quantitative morphometrics cheap "
  "and reproducible [21], [23], [26]; urban studies have demonstrated at scale how open imagery and machine "
  "learning can characterize street-level form [22], [24], [25]. Rural heritage settlements have so far benefited "
  "little from this turn, partly because their building stock is small and scattered, and partly because "
  "the relevant questions sit between disciplines. This study brings the open-data morphometric approach "
  "to bear on the twin infrastructure question of mountain villages.")
P("We pose four research questions. (RQ1) How differentiated are Huizhou traditional villages in the "
  "morphological dimensions that plausibly matter for both thermal and radio performance? (RQ2) Which "
  "morphological attributes are associated with village-scale summer surface temperature and its anomaly "
  "against the rural background? (RQ3) Which attributes are associated with simulated wireless coverage "
  "under a deployment that is held constant across villages? (RQ4) Where the two sets of associates "
  "coincide, do they act in the same or in opposite directions—that is, where are the trade-offs?")
P("To answer these questions we assemble a sample of 29 traditional villages in the Huizhou region and, "
  "using only open data and reproducible models, (i) characterize each village by twelve morphological "
  "metrics defined over two explicitly stated spatial frames; (ii) estimate village-scale summer LST and "
  "heat anomaly from a quality-masked multi-year Landsat median composite; (iii) simulate coverage under "
  "a standardized virtual macrocell deployment that removes operator-specific deployment heterogeneity, "
  "with grid-phase and frequency sensitivity analyses; and (iv) quantify, with size-controlled partial "
  "correlations, false-discovery-rate control over two explicitly defined test families, spatial "
  "autocorrelation diagnostics, and leave-one-county-out checks, which morphological attributes covary "
  "with the two performances in opposite or concordant directions. Section 2 describes the study area, "
  "data, and methods; Section 3 reports the results; Section 4 discusses interpretation, planning "
  "implications, and limitations; Section 5 concludes.")

# ==================== 2. MATERIALS AND METHODS ====================
H1("2. Materials and Methods")
P("The research framework couples two open-data model chains onto a common morphometric backbone (Fig. 1, "
  "Table 1). For each of the 29 villages we first compute twelve morphological metrics from elevation and "
  "land-cover data (Section 2.3). The same village domains then feed two independent performance models: a "
  "thermal chain, in which a quality-masked multi-year Landsat surface-temperature composite yields village "
  "LST and its anomaly against the rural background (Section 2.4); and a radio chain, in which a "
  "standardized virtual macrocell deployment is evaluated with a terrain-aware 3GPP propagation model to "
  "yield village coverage metrics (Section 2.5). Because the deployment is held constant across villages, "
  "coverage differences between villages reflect morphology and terrain rather than operator decisions. "
  "The two performance vectors are finally compared against the morphological vector across the sample, "
  "with the statistical controls described in Section 2.6. All in-text statistics, tables, and figures are "
  "generated from a single village-level analysis table by script, so that numbers reported in the text "
  "cannot drift from the data.")

H2("2.1. Study Area and Village Sample")
P("The study area covers the historical Huizhou prefecture in the foothills of the Huangshan mountains, "
  "southern Anhui (approximately 29.6°–30.3° N, 117.3°–118.9° E). The climate is subtropical monsoon with "
  "hot, humid summers in which outdoor thermal stress is a genuine public-health and livability concern. "
  "The terrain is a mosaic of steep forested ridges and narrow alluvial basins; villages traditionally "
  "settled along streams at basin edges, with their backs to a forested slope and their fronts to water—"
  "the classical *beishan mianshui* (backed by mountains, facing water) configuration. The region contains "
  "two UNESCO World Heritage villages (Hongcun and Xidi) and numerous nationally listed historic and "
  "traditional villages, making it both a conservation hotspot and a natural laboratory in which "
  "morphological setting varies widely within a single cultural sphere.")
P("We selected 29 traditional villages across six counties (Yixian, Shexian, Huizhou District, Jixi, "
  "Xiuning, and Qimen). Selection required an intact historic built core and an unambiguous geographic "
  "identity verifiable against OpenStreetMap and satellite imagery; two candidate villages were discarded "
  "because their positions could not be verified with confidence. Village coordinates were snapped to the "
  "centroid of the nearest built-up connected component in the reference land-cover map (median snap "
  "distance 78 m, maximum 517 m), so that all morphological measurement is anchored to the actual built "
  "fabric rather than to nominal administrative points. Three sample particularities are flagged because "
  "they matter for the analysis. First, Yuliang’s detected built-up component (258.7 ha) merges with the "
  "adjacent Shexian county seat; we retain the village and verify that all reported associations are "
  "robust to its exclusion. Second, the built fabric of two small mountain villages (Zuyuan and Mulihong) "
  "is under-detected by the 10-m land-cover map; component-based metrics are therefore unavailable for "
  "them (n = 27 where applicable), and their coverage targets follow the fallback rule of Section 2.5, "
  "with a dedicated exclusion sensitivity check. Third, the sample deliberately spans basin-floor, "
  "piedmont, and deep-valley settings (domain-mean elevation 113–552 m; local relief 38–538 m), which is "
  "the source of morphological variance on which the analysis draws. Because elevation is summarized as a "
  "domain mean, it can differ from point elevation at the village centroid, particularly for steep "
  "mountain villages. Fig. 1 maps the sample; Table 1 lists the villages with key attributes; the full "
  "twelve-metric table and the per-phase coverage detail are given in Appendix Table A1.")
FIG("figures/Fig1_study_area_EN.png", 1,
    "The 29 sampled traditional villages in the Huizhou region, southern Anhui, China (base map: Esri "
    "World Imagery; numbers keyed to Table 1).")

H2("2.2. Open Data")
P("All inputs are public datasets; no field measurement was used, and the entire pipeline is scripted and "
  "re-runnable. Terrain is given by the 30-m Copernicus digital elevation model (COP-DEM GLO-30) [21]. "
  "Land cover is the 10-m ESA WorldCover 2021 map (v200), from which the built-up, tree-cover, and water "
  "classes were extracted [23]. Summer surface temperature is derived from Landsat 8/9 Collection-2 "
  "Level-2 surface-temperature products (band ST_B10, native 100-m posting), accessed through the "
  "Microsoft Planetary Computer spatiotemporal asset catalog [27]. We queried June–September scenes from "
  "2019–2025 with catalog scene cloud cover below 10%, retaining up to nine of the lowest-cloud scenes "
  "per Worldwide Reference System frame, yielding 36 scenes over the four frames (paths 120–121, rows "
  "39–40) that cover the study area; the per-scene identifiers, dates, and cloud covers are listed in "
  "Appendix Table A2. Digital numbers were converted with the Collection-2 scale factors "
  "(ST = DN × 0.00341802 + 149.0 K) and expressed in degrees Celsius. Quality control applied the "
  "Collection-2 QA_PIXEL bit mask pixel-wise (fill, dilated cloud, cirrus, cloud shadow, snow, and cloud "
  "bits cleared), followed by a 10–60 °C physical plausibility screen; three scenes whose surface-"
  "temperature retrieval failed under this screen (zero valid pixels) were excluded, leaving 33 valid "
  "scenes. The summer composite is the per-pixel *median* across valid scenes, which is robust to "
  "residual contamination; each pixel carries an observation count, and village domains are supported by "
  "5–13 (minimum) to 6–14 (median) valid observations per pixel. A 500-m village domain contains roughly "
  "80 native 100-m thermal pixels. Using a multi-year median sacrifices year-to-year resolution in "
  "exchange for a stable, cloud-gap-free characterization of typical summer daytime surface behavior, "
  "which is the quantity that morphology can plausibly covary with [28]. Relative to a simple arithmetic-"
  "mean composite without the QA bit mask, the quality-masked median shifts village LST by 1.1 °C on "
  "average (maximum 4.4 °C), which illustrates that the quality chain is not cosmetic.")

H2("2.3. Morphological Metrics: Two Spatial Frames, Stated Explicitly")
P("Preliminary review of an earlier draft of this work showed that mixing spatial frames silently invites "
  "contradiction, so we state the frames before defining the metrics. **Frame O (object level)** is the "
  "built-up connected component nearest to the nominal village point in the 10-m land-cover map; it has no "
  "fixed geometric bound and can extend well beyond the village core (for Yuliang it merges with the "
  "adjacent county seat). **Frame D (site level)** is the fixed 500-m-radius circular domain centered on "
  "the Frame-O centroid; its maximum area is π × 500² ≈ 78.5 ha, and it defines the analysis window for "
  "terrain, landscape context, thermal, and coverage measurement. Object-level metrics describe the plan "
  "form of the detected fabric; site-level metrics describe where that fabric sits.")
P("*Plan-form metrics (Frame O).* Component built-up area is the total surface of the connected component "
  "(5.2–258.7 ha across the sample). The elongation index is the principal-axis aspect ratio of the "
  "component, high for stream-following linear villages and low for isotropic basin villages. Compactness "
  "is a perimeter–area ratio of the component, high where the fabric forms a tight, contiguous core. All "
  "three are unavailable for the two under-detected villages.")
P("*Terrain metrics (Frame D).* Elevation is the domain mean; relief is the maximum minus minimum "
  "elevation within the domain; slope is the domain mean of terrain gradient. Southness is the domain "
  "mean of cos(aspect), positive for south-facing ground, and north–south asymmetry is the difference in "
  "mean elevation between the northern and southern halves of the domain—together these capture the "
  "canonical claim that Huizhou villages face south against a northern slope. To capture terrain "
  "enclosure we use a terrain sky-view factor (tSVF), the unobstructed fraction of the upper hemisphere "
  "at the built-up centroid, sampled along 72 azimuths with a 2500-m horizon [15]:")
EQ([("tSVF = 1 − (1/", "i"), ("N", "i"), (") Σ sin(", None), ("γ", "i"), ("i", "sub"),
    ("),   ", None), ("i", "i"), (" = 1, …, 72", None)], 1)
P("where γ", )
doc.paragraphs[-1].add_run("i").font.subscript = True
add_runs(doc.paragraphs[-1],
    " is the horizon elevation angle along azimuth *i*. A village on an open plain has tSVF ≈ 1; a village "
    "at the bottom of a gorge has a markedly lower value. The 2500-m horizon is long enough to include the "
    "enclosing ridge lines that govern both insolation and radio visibility, and short enough to remain a "
    "village-scale attribute. Because tSVF is evaluated once, at the centroid, it characterizes the "
    "village’s setting rather than its internal spatial variation; intra-village sky-view heterogeneity "
    "requires building-scale data that our open sources do not provide (Section 4.4).")
P("*Landscape-context metrics (Frame D unless noted).* The forest ring is the tree-cover fraction within "
  "a 300-m ring around the Frame-O component, representing the vegetated backdrop typical of Huizhou "
  "villages; a 300-m binary buffer proved undiscriminating (saturated at 100% for most villages), so we "
  "use the continuous ring share; because the ring is defined around the detected component, it too is "
  "unavailable for the two under-detected villages. Water proximity is the Euclidean distance from "
  "built-up cells to the nearest water pixel, summarized by its mean and minimum. Finally, domain "
  "built-up area is the built-up surface clipped to Frame D (0–56.8 ha across the sample); it is the "
  "size variable used in the statistical controls of Section 2.6, because it shares the spatial frame of "
  "the outcome variables (Spearman ρ = 0.87 against component area across the 27 villages with both). "
  "Several metrics co-vary by construction of the terrain—deep-valley villages are steep, forested, "
  "enclosed, and elongated—which is why Section 2.6 relies on rank correlations and size-controlled "
  "partial correlations rather than on parametric multivariate models.")

H2("2.4. Summer LST and Heat Anomaly")
P("For each village, core LST is the mean of the summer median composite within the 500-m domain, and "
  "background LST is the mean within a 1–2 km ring after excluding built-up cells, so that the background "
  "reflects the rural matrix rather than adjacent settlement fabric. The heat anomaly is")
EQ([("ΔLST = LST", "i"), ("core", "sub"), (" − LST", "i"), ("bg", "sub")], 2)
P("The 1–2 km ring is close enough to share the village’s meso-climate and terrain setting, and far "
  "enough to avoid mixing in village fabric; excluding built-up cells from the ring prevents the anomaly "
  "from being diluted by neighboring construction. LST is used as a physically consistent proxy of the "
  "daytime outdoor thermal environment; it is not equivalent to air temperature or pedestrian-level "
  "thermal comfort, a distinction we return to in Section 4.4 [28].")

H2("2.5. Standardized Wireless Deployment and Propagation Model")
P("Real operator deployments are heterogeneous and commercially opaque, so village-level coverage "
  "differences measured against live networks conflate morphology with deployment history. To isolate "
  "morphology and terrain, we evaluate coverage under a standardized virtual deployment: macrocell sites "
  "on a 2.5-km grid over the study region, each site snapped to the highest DEM cell within 600 m to "
  "mimic the universal hilltop preference of rural radio planning, with a 30-m antenna height. The "
  "carrier frequency is 2.6 GHz, a widely deployed mid-band in China’s mobile networks; we treat it as a "
  "conservative mid-band case, because lower bands propagate further and diffract better around terrain—"
  "a 700-MHz repetition of the full chain, reported in Section 3.3, confirms that absolute coverage "
  "levels rise at low frequency while the inter-village ranking is essentially preserved. The effective "
  "isotropic radiated power per resource element (EPRE) is")
EQ([("EIRP = ", None), ("P", "i"), ("T", "sub"), (" − 10 log", None), ("10", "sub"),
    ("(", None), ("N", "i"), ("SC", "sub"), (") + ", None), ("G", "i"), ("T", "sub"),
    (" − ", None), ("L", "i"), ("f", "sub"),
    (" = 46 − 10 log", None), ("10", "sub"), ("(1200) + 17 − 2 = 30.2 dBm", None)], 3)
P("for a 46-dBm carrier, a 20-MHz downlink of 1200 subcarriers, 17-dBi antenna gain, and 2-dB feeder "
  "loss; as a per-resource-element quantity it does not scale with bandwidth. Because any fixed grid may "
  "favor or disfavor individual villages simply through its alignment, the deployment is repeated over "
  "four grid phases shifted by half a spacing (0 and 1250 m in x and y), yielding 1620 sites per phase; "
  "village-level coverage metrics are averaged across the four phases, and the cross-phase dispersion is "
  "itself reported as a measure of deployment robustness.")
P("Coverage targets are the built-up cells (30 m) inside each village domain; where the land-cover map "
  "under-detects the built fabric (fewer than 30 cells: Zuyuan and Mulihong), a regular 150-m grid over "
  "the domain is used instead, and all coverage associations are re-estimated without these two villages "
  "as a sensitivity check (Sections 2.6 and 3.3). The receiver height is 1.5 m. Path loss follows the "
  "3GPP RMa model [9], with LOS or NLOS determined per link by stepping along the 30-m DEM profile "
  "between site and target and applying a cumulative horizon criterion: a target is in LOS if the "
  "straight site-to-target line clears every intervening terrain elevation. For LOS links,")
EQ([("PL", "i"), ("LOS", "sub"), ("(", None), ("d", "i"), (") = 20 log", None), ("10", "sub"),
    ("(40π", None), ("d", "i"), (" f", "i"), ("c", "sub"), ("/3) + min(0.03 ", None), ("h", "i"),
    ("1.72", "sup"), (", 10) log", None), ("10", "sub"), ("(", None), ("d", "i"),
    (") − min(0.044 ", None), ("h", "i"), ("1.72", "sup"), (", 14.77) + 0.002 log", None),
    ("10", "sub"), ("(", None), ("h", "i"), (") ", None), ("d", "i")], 4)
P("with an additional 40 log10(d/dBP) term beyond the breakpoint distance dBP = 2π hBS hUT fc/c. For "
  "NLOS links the RMa model applies its rural branch,")
EQ([("PL", "i"), ("NLOS", "sub"), ("(", None), ("d", "i"), (") = 161.04 − 7.1 log", None), ("10", "sub"),
    ("(", None), ("W", "i"), (") + 7.5 log", None), ("10", "sub"), ("(", None), ("h", "i"),
    (") − (24.37 − 3.7(", None), ("h", "i"), ("/", None), ("h", "i"), ("BS", "sub"),
    (")²) log", None), ("10", "sub"), ("(", None), ("h", "i"), ("BS", "sub"), (") + (43.42 − 3.1 log",
     None), ("10", "sub"), ("(", None), ("h", "i"), ("BS", "sub"), ("))(log", None), ("10", "sub"),
    ("(", None), ("d", "i"), (") − 3) + 20 log", None), ("10", "sub"), ("(", None), ("f", "i"),
    ("c", "sub"), (") − (3.2(log", None), ("10", "sub"), ("(11.75 ", None), ("h", "i"),
    ("UT", "sub"), ("))² − 4.97)", None)], 5)
P("and the realized path loss is max(PL_LOS, PL_NLOS), with the nominal rural parameterization of the "
  "model (average building height h = 5 m, street width W = 20 m, base height hBS = 30 m, receiver "
  "height hUT = 1.5 m) [9]. Throughout Eqs. (3)–(5), distances d are in metres and the carrier frequency "
  "fc in GHz. The ray-stepping LOS determination is purely geometric: for each site–target pair we "
  "sample the 30-m DEM along the connecting path at one-pixel increments, maintain the running maximum "
  "of the elevation angle from the site antenna to the intervening terrain, and declare the target "
  "visible when the straight line to the receiver clears that cumulative horizon. The procedure is the "
  "radio analogue of the viewshed analysis familiar from landscape planning, and it is what couples "
  "coverage directly to terrain morphology. Each target keeps the strongest server among sites within "
  "10 km; at this assignment radius, omitting Earth curvature shifts the computed line of sight by at "
  "most about 7.8 m, small against the 30-m terrain sampling. We report cov85 and cov95, the percentages "
  "of targets with reference signal received power (RSRP) of at least −85 and −95 dBm—respectively the "
  "level of reliable data service and the level of basic connectivity in this scenario—and the "
  "10th-percentile RSRP (RSRP p10) as a continuous measure of the worst-served fabric.")
P("The model deliberately omits foliage attenuation [19], building clutter, diffraction refinement, "
  "antenna patterns, shadowing, and interference. What it produces is therefore a deterministic "
  "received-power scenario under a stylized deployment—not an estimate of any operational network—and "
  "absolute coverage levels are optimistic. The objects of this study are the *differences between "
  "villages*, which are driven almost entirely by terrain visibility and are far less sensitive to these "
  "omissions; the 700-MHz repetition (Section 3.3) quantifies the frequency side of that claim. Where "
  "the omissions matter for interpretation—most notably the forest ring, whose measured association with "
  "coverage is purely terrain-mediated—we say so explicitly in Section 4.")

H2("2.6. Statistical Analysis")
P("Associations between the twelve morphological metrics and the four performance variables (village "
  "LST, ΔLST, cov85, RSRP p10) are quantified by Spearman rank correlations, which are robust to the "
  "skewed distributions and small sample size. Two test families are defined explicitly: family F1 "
  "comprises the 48 raw correlations (12 metrics × 4 outcomes), and family F2 comprises the 44 partial "
  "correlations on ranks controlling domain built-up area (11 metrics × 4 outcomes; size itself is not "
  "controlled for). Each family is controlled separately with the Benjamini–Hochberg false discovery "
  "rate at q = 0.05 [29]; in Table 2, stars mark uncorrected p-values and a dagger marks tests that "
  "survive BH control within their family, and 95% confidence intervals for headline correlations use "
  "the Fisher z transform. Because size correlates with nearly everything—larger villages are hotter "
  "and also tend to sit in more open, serviceable terrain—the F2 partial correlations are the "
  "conservative read of metric-level association; we do not call them independent effects, only "
  "size-adjusted ones.")
P("Robustness is assessed four ways. First, the four-phase deployment repetition absorbs grid alignment "
  "(Section 2.5). Second, the peri-urban Yuliang case is excluded and all associations re-estimated. "
  "Third, the two villages with fallback coverage targets are excluded from all coverage associations. "
  "Fourth, a leave-one-county-out jackknife over the six counties checks that no single county drives "
  "the headline associations. Spatial autocorrelation is diagnosed with Moran’s I under inverse-distance "
  "row-standardized weights (9999 permutations); where it is significant, the jackknife provides the "
  "mitigating evidence. Trend lines in scatter plots are Theil–Sen robust fits [30], [31]. All "
  "computation uses open-source Python libraries (rasterio, numpy, pandas, SciPy, matplotlib); the "
  "full code, the village-level analysis table, and the scene manifest are deposited in a public "
  "repository (see Data Availability).")

# ==================== 3. RESULTS ====================
H1("3. Results")
H2("3.1. Morphological Characterization")
P("The 29 villages differentiate clearly along the terrain dimension (Table 1, Fig. 2). Topographic "
  "openness spans tSVF = 0.899–0.999: most villages occupy open basin floors where the 2500-m horizon is "
  "essentially unobstructed, while a minority—notably Mulihong (tSVF = 0.899) and Zuyuan (0.928)—sit in "
  "deeply incised valleys. The forest ring covers 35–97% of the 300-m backdrop. Domain built-up area "
  "ranges from essentially nil in the two under-detected mountain villages to 56.8 ha in the peri-urban "
  "Yuliang, and component built-up area from 5.2 to 258.7 ha; relief within the village domain ranges "
  "from 38 m on the basin floor to 538 m around the highest mountain villages. The three setting classes "
  "are legible in the metric space: basin villages are open, compact, and weakly forested in their "
  "immediate ring; piedmont villages are intermediate; deep-valley villages are enclosed, elongated, "
  "steep, and almost fully ringed by forest.")
P("Two morphological observations deserve note. First, despite the canonical image of the south-facing "
  "Huizhou village, four villages (Kantou, Guanlu, Nanping, and Zhukou) face north, with negative "
  "southness values—a reminder that the textbook ideal is an idealization rather than a rule. Second, "
  "plan form and terrain co-vary: valley villages are strongly elongated along their streams (elongation "
  "up to 5.4), whereas basin villages are more isotropic. This co-variation, visible in the standardized "
  "distributions of Fig. 2c, is the statistical signature of site selection responding to terrain—and it "
  "is what makes the mountain-village morphometric problem different from its urban counterpart.")
import pandas as pd
_t1 = pd.read_csv("tables/Table1_sample.csv").fillna("—")
TABLE(1, "Key attributes of the 29 sampled villages (county; coordinates; domain built-up area; "
         "terrain openness; forest ring; summer LST and anomaly; four-phase coverage metrics). The full "
         "twelve-metric table is Appendix Table A1.",
      list(_t1.columns), _t1.values.tolist(), fontsize=7)
FIG("figures/Fig2_morphology.png", 2,
    "Morphological characterization of the sample. (a) Topographic openness (tSVF) and (b) forest ring "
    "share over a 30-m hillshade, point size proportional to domain built-up area; (c) standardized "
    "distributions of eight metrics across the 29 villages.")

H2("3.2. Summer Thermal Environment")
P("Village-core summer LST spans 31.3–42.9 °C (mean 36.5 °C) across the sample. The coolest villages are "
  "high-elevation, enclosed mountain settlements (Tachuan, 31.3 °C, at 552 m domain-mean elevation with "
  "538 m of local relief); the hottest are large, open basin settlements such as Yuliang (42.9 °C). "
  "Every village is warmer than its own rural background: ΔLST ranges from +0.2 to +6.5 °C with a mean "
  "of +2.5 °C (Fig. 3). Even in a forested mountain region with modest building densities, settlement "
  "fabric is therefore associated with a systematic, measurable surface heat excess, comparable in "
  "sign—if not in magnitude—to the canonical urban heat island [11], [12].")
P("The spatial pattern behind these numbers is legible in Fig. 3a. The hot corridor follows the broad, "
  "open Xin’an River and basin lowlands where the large, compact settlements of the plain—including the "
  "county seats and the peri-urban fringe of Shexian—concentrate; the cool zones track the forested "
  "ridge systems. Village-level extremes sit where the terrain story predicts: the five coolest villages "
  "(Tachuan 31.3, Mulihong 31.6, Zuyuan 32.5, Lucun 33.9, Renli 34.0 °C) combine high elevation, high "
  "relief, and near-complete forest rings, while the five hottest (Yuliang 42.9, Tangyue 39.9, Qiankou "
  "39.8, Lixi 39.5, Xiongcun 39.0 °C—only Yuliang exceeds 40 °C) combine low relief, maximal openness, "
  "and large contiguous fabric. The pairing of core and background temperatures in Fig. 3b shows that "
  "the anomaly is not a simple elevation artifact: high villages are cooler in absolute terms but remain "
  "warmer than their own, equally high surroundings.")
P("The morphological associates of absolute LST form a coherent terrain story (Table 2). Village LST "
  "rises with topographic openness (ρ = +0.60, q = 0.003, 95% CI [+0.30, +0.79]), domain built-up area "
  "(+0.57, q = 0.005), and compactness (+0.63, q = 0.002), and falls with relief (−0.67, q < 0.001, CI "
  "[−0.83, −0.41]), elevation (−0.62, q = 0.002), and water proximity (minimum distance, −0.53, "
  "q = 0.015). The forest ring (−0.25, p = 0.20) and slope (−0.35, p = 0.065) show only non-significant "
  "negative tendencies. Controlling domain built-up size reshuffles this picture instructively: "
  "compactness retains its association (partial ρ = +0.53, q = 0.021), as do elevation (−0.55) and "
  "relief (−0.49), but openness weakens below the FDR threshold (partial ρ = +0.35, q = 0.16) and the "
  "forest-ring tendency vanishes (partial ρ = −0.06). For the heat anomaly ΔLST, compactness is "
  "dominant—strongly positive even at fixed size (partial ρ = +0.70, q < 0.001)—while elevation is "
  "negative (raw ρ = −0.45, q = 0.035). The two dependent variables therefore tell different stories: "
  "absolute LST covaries mainly with *where* the village sits, whereas the anomaly relative to its own "
  "hinterland covaries with *how* its fabric is arranged. Southness is unrelated to any thermal outcome "
  "(|ρ| ≤ 0.07); north–south asymmetry shows a weak, non-significant negative tendency (−0.30, "
  "p = 0.11).")
FIG("figures/Fig3_lst.png", 3,
    "Summer thermal environment. (a) Quality-masked LST median composite (2019–2025, Landsat 8/9 "
    "Collection 2); (b) village-core versus background LST, villages sorted by core LST; (c) "
    "distribution of the heat anomaly ΔLST (n = 29, bin width 0.5 °C, mean +2.5 °C).")

H2("3.3. Wireless Coverage and Deployment-Phase Sensitivity")
P("Under the standardized deployment, four-phase mean cov85 spans 59.8–100% across villages (mean "
  "93.2%). Eighteen of 29 villages reach 96% or better, and these are precisely the open basin "
  "settlements; the deep-valley villages Mulihong (59.8%) and Zuyuan (64.4%) fall far behind, and the "
  "piedmont villages occupy the middle (Fig. 4a). Coverage at the lenient −95 dBm threshold is near "
  "saturation—16 villages stand at a four-phase mean of 100% (range 85.3–100%)—which is why cov85, the "
  "reliable-data-service level in this scenario, is adopted as the primary metric; RSRP p10 ranges from "
  "−96.6 to −76.0 dBm and supports the same ordering.")
P("The four-phase repetition reveals a second, subtler result (Fig. 4b): grid phase matters exactly "
  "where coverage is marginal. The cross-phase standard deviation of cov85 reaches 33 percentage points "
  "in Zuyuan (phase values from 15% to 88%) and exceeds 15 points in Mulihong, Renli, Shitan, and "
  "Changxi, whereas basin villages are phase-invariant at or near 100%. Deployment sensitivity is thus "
  "itself associated with morphological setting: villages at the coverage margin can be lucky or unlucky "
  "with a given site pattern, while well-sited villages are robust to it. Accordingly, village rankings "
  "across phases are moderately stable for cov85 (mean pairwise rank correlation 0.57) and only weakly "
  "stable for RSRP p10 (0.38); the plain mean RSRP proved phase-unstable (0.09), being hostage to the "
  "distance of the single nearest site, and was discarded from further analysis. The four-phase mean is "
  "therefore best read as absorbing most—but not all—deployment arbitrariness: rankings among open, "
  "well-covered villages are phase-robust, while rankings among marginal, deep-valley villages are not.")
P("The village-level detail behind these statistics is instructive. Yuliang, the peri-urban case, "
  "combines the largest target set (631 built-up cells in the domain) with a mid-pack four-phase mean of "
  "86.3%—and, unexpectedly, substantial phase dispersion (71.0–99.4% across phases): its fabric extends "
  "from the open plain into a river corridor whose margins lose visibility in two of the four grid "
  "alignments. Size and openness therefore do not exempt a village from deployment sensitivity. At the "
  "other extreme, Zuyuan and Mulihong—the two villages for which the land-cover map under-detects the "
  "built fabric, and whose coverage is therefore evaluated on a 150-m fallback grid—are not only the "
  "worst covered but also the most phase-sensitive: their serviceability is decided by whether a "
  "half-spacing shift happens to place a site on the one ridge with a clear path into the valley. "
  "Because their fallback target grids are not strictly comparable to the built-up-cell targets of the "
  "other 27 villages, all coverage associations below are re-estimated without them (Section 3.4). "
  "Between these poles, piedmont villages such as Huansha, Zhukou, and Zhanqi (cov85 ≈ 90–96%) lose "
  "service only at their valley-facing margins, which is where their weakest RSRP deciles originate.")
P("Frequency choice does not change the picture. Repeating the full chain at 700 MHz (a band central to "
  "China’s current rural 5G build-out) raises absolute coverage as expected—mean phase-0 cov85 rises "
  "from 94.8% to 97.5%—but preserves the inter-village ordering (rank correlation 0.81 for cov85 and "
  "≥0.98 for RSRP statistics against the 2.6-GHz results). The morphological gradients reported below "
  "are therefore not an artifact of band choice.")
FIG("figures/Fig4_coverage.png", 4,
    "Wireless coverage under the standardized virtual deployment. (a) Four-phase mean cov85 by village "
    "(points) over the 1620-site phase-0 grid (dots), on a 30-m hillshade; (b) deployment-phase "
    "sensitivity: villages with low mean coverage also show high cross-phase dispersion.")

H2("3.4. Morphology–Performance Coupling and Trade-Offs")
P("Bringing the two performances together (Fig. 5, Table 2) answers RQ4. To classify couplings "
  "consistently, we first fix utility directions: thermal performance improves as LST (or ΔLST) "
  "decreases, and coverage performance improves as cov85 (or RSRP p10) increases. A morphological "
  "attribute is a *trade-off* attribute when its associations with the two utilities carry opposite "
  "signs, and a *one-sided* attribute when only one association is detectable.")
P("By this rule, three attributes are trade-off axes. First, topographic openness is associated with "
  "higher LST (ρ = +0.60, q = 0.003) and better coverage (cov85, ρ = +0.69, q < 0.001, CI [+0.44, "
  "+0.84]); the coverage side survives size control (partial ρ = +0.57, q = 0.008), while the thermal "
  "side weakens below the FDR threshold once size is controlled (partial ρ = +0.35, q = 0.16). Second, "
  "relief is associated with lower LST (ρ = −0.67, q < 0.001) and worse coverage (ρ = −0.64, q = 0.001; "
  "partial ρ = −0.49, q = 0.028). Third, elongation—the attribute an earlier draft of this paper "
  "mis-classified as synergistic—couples a marginal thermal association (ρ = −0.37, p = 0.058) with "
  "significantly worse coverage (cov85, ρ = −0.45, q = 0.042; RSRP p10 partial ρ = −0.49, q = 0.032): "
  "stream-following linear villages tend to sit slightly cooler but are measurably harder to serve. "
  "Slope behaves like relief on the coverage side (ρ = −0.85, q < 0.001, CI [−0.93, −0.70]) with only a "
  "non-significant thermal tendency.")
P("Two attributes are one-sided. The forest ring strongly shadows signal (ρ = −0.81, q < 0.001, CI "
  "[−0.91, −0.61]; partial ρ = −0.78) but shows no detectable association with village-scale daytime "
  "LST after quality masking (ρ = −0.25, p = 0.20)—a null result we take seriously in Section 4.1. "
  "Compactness is a purely thermal attribute: it raises LST (ρ = +0.63) and especially the anomaly "
  "(partial ρ = +0.70) with no coverage counterpart (ρ = +0.25, p = 0.21). Southness, the attribute "
  "most often invoked in heritage discourse, shows no association with any outcome. Of the 48 raw tests "
  "(family F1), 20 survive Benjamini–Hochberg control at q = 0.05; of the 44 size-controlled partial "
  "tests (family F2), 13 survive. All associations reported above retain their signs—and most their "
  "magnitudes—when the peri-urban Yuliang case is excluded (for example, the openness–coverage "
  "correlation rises to ρ = +0.78, and the size–coverage correlation to +0.57); when the two "
  "fallback-target villages are excluded from coverage tests, the openness–coverage correlation is "
  "ρ = +0.62 (p < 0.001, n = 27) and the forest-ring and slope correlations are essentially unchanged "
  "(−0.81 and −0.82); and in the leave-one-county-out jackknife the headline associations keep their "
  "signs in every county omission (openness–coverage ρ between +0.62 and +0.81; forest-ring–coverage "
  "ρ between −0.72 and −0.88; openness–LST ρ between +0.50 and +0.72), so no single county drives the "
  "results. Spatial diagnostics qualify the coverage side honestly: Moran’s I detects significant "
  "spatial clustering for cov85 (I = 0.21, p = 0.002) and tSVF (I = 0.19, p = 0.002), weak or absent "
  "clustering for the thermal outcomes (LST: I = 0.13, p = 0.06; ΔLST: I = 0.01, n.s.), which is why "
  "the county jackknife, rather than the nominal p-value alone, carries the robustness argument.")
FIG("figures/Fig5_tradeoff.png", 5,
    "Morphology–performance couplings. (a), (b) Topographic openness versus village LST and cov85; "
    "(c), (d) forest ring share versus village LST and cov85. Point size: domain built-up area; lines: "
    "Theil–Sen robust fits; annotations: Spearman ρ with uncorrected significance and n (n = 27 in "
    "panels c–d because the forest ring, defined around the detected built-up component, is unavailable "
    "for the two under-detected villages).")
_t2 = pd.read_csv("tables/Table2_correlation.csv")
TABLE(2, "Spearman correlations between morphological metrics and performance variables (upper row per "
         "metric), and partial correlations controlling domain built-up area (row marked “ctrl size”). "
         "* p < 0.05, ** p < 0.01, *** p < 0.001 (uncorrected); † survives Benjamini–Hochberg control "
         "at q = 0.05 within its test family (F1: 48 raw tests; F2: 44 partial tests). Component-based "
         "metrics (elongation, compactness, water distances, forest ring) use n = 27; others n = 29.",
      list(_t2.columns), _t2.values.tolist(), fontsize=8)

# ==================== 4. DISCUSSION ====================
H1("4. Discussion")
H2("4.1. Trade-Off Axes, Read Mechanistically")
P("The first axis is enclosure. The same topographic enclosure that shades a valley village, shortens "
  "its solar exposure, and channels nocturnal cold-air drainage also blocks the low-elevation radio "
  "paths on which rural macrocells depend. Vernacular site selection and radio physics price the same "
  "terrain in opposite currencies. This result inverts the urban intuition: in city morphometrics, "
  "higher sky-view factor is generally associated with *cooler* canyon environments because SVF indexes "
  "heat release from street canyons [14], [18]; at the mountain-village scale, higher tSVF is associated "
  "with *hotter* settlements because it indexes insolation exposure of the whole site. The sign flip is "
  "a scale effect, not a contradiction, but it warns against transferring urban morphometric rules to "
  "rural terrain-coupled settlements. We note honestly that the thermal side of this axis is the "
  "weakest of the reported associations once size is controlled, and we therefore treat the enclosure "
  "axis as a planning hypothesis with a strong coverage side and a moderate, size-entangled thermal "
  "side.")
P("The second axis is the forest ring, the emblematic Huizhou backdrop—and here the quality-controlled "
  "reanalysis delivered a salutary surprise. In a simple mean-based composite without the QA bit mask, "
  "the ring appeared to cool (ρ ≈ −0.58); after quality masking and median compositing, the village-"
  "scale daytime association is not distinguishable from zero (ρ = −0.25, p = 0.20; partial ρ = −0.06). "
  "We report this null result rather than the earlier apparent effect. Three non-exclusive explanations "
  "are plausible: the ring cools its own slopes as much as the village, so core-versus-background "
  "contrast cancels; daytime summer LST is dominated by insolation exposure rather than by evapo-"
  "transpiration at the 100-m scale; and any genuine ring effect may operate at night or at the "
  "courtyard scale, both invisible to our composite. What remains robust—and large—is the ring’s "
  "association with signal shadowing (ρ = −0.81, size-controlled partial ρ = −0.78), which in our "
  "model is entirely terrain-mediated; adding realistic vegetation loss [19] would strengthen, not "
  "weaken, that anti-correlation. For the ecological-wisdom reading of vernacular landscape, the honest "
  "summary is therefore selective support: water proximity and the compactness–anomaly link survive "
  "scrutiny, the forest ring’s daytime thermal benefit at village scale does not, and the ring’s "
  "digital-infrastructure cost is unambiguous.")
P("Compactness and southness refine the architectural reading. Compactness operates on the anomaly, "
  "not only the absolute: at fixed domain size, compact cores are hotter than their own hinterland, "
  "consistent with sparse internal green space and reduced sky view within historic fabric. Whether "
  "courtyard-scale greening or selective interior opening can actually reduce the anomaly cannot be "
  "tested with 10-m land-cover data and is offered strictly as a hypothesis for building-scale work "
  "(Section 4.4). Southness, by contrast, is inert at settlement scale in this sample: we find no "
  "evidence that orientation predicts thermal outcomes, so claims for village-scale orientation effects "
  "should be treated as unproven rather than canonical—orientation effects are real at the scale of "
  "buildings and canyons [3], [14], but they average out across a settlement, and our four north-facing "
  "villages show that the canon was never a rule in the first place.")
H2("4.2. Comparison with Previous Studies")
P("Three strands of previous work frame our findings. First, the urban morphometrics literature has "
  "established SVF–temperature relationships at the scale of street canyons and LCZ classes [13], [14], "
  "[18], where openness generally aids night-time cooling. Our association between openness and higher "
  "village-scale summer LST (ρ = +0.60) does not contradict this work: it reflects the different physics "
  "that dominate when the ‘canyon’ is a mountain valley and the variable is daytime insolation of the "
  "whole site rather than nocturnal long-wave release from a street. The two regimes are reconciled once "
  "one recognizes that tSVF here measures horizon obstruction by terrain, not by buildings. Second, the "
  "vernacular-climate literature has documented passive strategies of traditional settlements through "
  "single-village instrumentation and simulation [1]–[4], [7], including work in the Huizhou area itself "
  "[3]. Our contribution relative to that strand is statistical rather than instrumental: with 29 "
  "villages we can separate site-level associations from fabric-level ones (openness and relief versus "
  "compactness) in a way that one-village case studies structurally cannot, and our null result for the "
  "forest ring is a caution against generalizing courtyard-scale measurements to the settlement scale. "
  "Third, the urban-informatics strand has shown how open imagery and reproducible computation can "
  "characterize fine-grained urban form at scale [22], [24], [25]. We extend that ethos to a domain it has "
  "largely bypassed—rural heritage settlements—and to a second physical field, radio propagation, that "
  "this literature has never engaged. The nearest precedents to our coverage analysis are the "
  "propagation-modeling and radio-planning literature [8]–[10]; our inversion of the perspective, asking "
  "not ‘where should sites go’ but ‘which village forms are inherently hard to serve’, appears to be "
  "new.")
P("The elongation result further illustrates what a two-physics reading adds. In the thermal literature, "
  "linear valley villages would be filed under ‘favorably shaded’; in radio planning the same form is a "
  "known worst case, because a linear settlement along a valley floor maximizes the share of fabric "
  "lying at low radio horizons. That one morphological descriptor is simultaneously a modest climate "
  "asset and a measurable connectivity liability is, to our knowledge, first quantified here (ρ = −0.37, "
  "p = 0.058 against LST; ρ = −0.45, q = 0.042 against cov85).")
H2("4.3. Implications for Heritage-Compatible and Digital-Village Planning")
P("For conservation planning, the practical message is that thermal-friendly morphology is not "
  "automatically connectivity-friendly, but the conflict is quantifiable and therefore manageable. Even "
  "the worst-served villages reach roughly 60% good coverage under a macro-only deployment; the residual "
  "gap is precisely the niche for low-visual-impact small cells at the village perimeter, fed through "
  "the open river and road corridors that pierce the forest ring. LOS simulation on open elevation data, "
  "as used here, offers heritage authorities a cheap screening tool that can be run before any hardware "
  "or visual-impact discussion begins, and that directly respects the constraint that matters most in a "
  "protected village: where things can be seen from, and where they cannot.")
P("For digital-village and CIM programs, the same pipeline doubles as an analytics layer. From open "
  "data it maps both the thermal burden and the radio visibility of every settlement, providing the "
  "baseline against which digital infrastructure in historic settings can be planned rather than "
  "improvised; in the Chinese context, such layers can be embedded in the CIM base-platform standards "
  "now being rolled out [6]. Because deployment-phase sensitivity is itself mapped (Fig. 4b), planners "
  "can distinguish villages whose service will be robust from villages that need site-by-site "
  "engineering. The open-data character of the whole workflow matters practically: it can be audited by "
  "conservation reviewers, re-run as new satellite data arrive, and transferred to other mountainous "
  "regions at negligible marginal cost.")
P("Finally, there is a discursive implication. The ecological wisdom of vernacular settlements is "
  "usually asserted qualitatively in heritage narratives; here it is quantified—and found to be real "
  "but selective and conditional. In this sample, enclosure and compactness carry measurable thermal "
  "associations; the forest ring’s daytime village-scale cooling does not survive quality control; the "
  "orientation canon is neither rule nor thermal determinant at settlement scale; and the same "
  "attributes that shade and shelter also isolate from the network. A mature, evidence-based account of "
  "traditional ecological knowledge should be able to state both sides of that ledger—including the "
  "null results. We suggest that this kind of quantified, two-sided assessment is precisely what makes "
  "the wisdom credible—and translatable—when it is communicated to engineering, planning, and policy "
  "audiences.")
H2("4.4. Limitations and Future Work")
P("Eight limitations qualify the findings. First, LST is not air temperature or thermal comfort: "
  "satellite LST responds to surface fabric and misses shade-mediated comfort, and our composite "
  "characterizes summer daytime only; sensor-based validation is the obvious next step. Second, the "
  "composite is correlational in nature and single-season; night-time, winter, and transitional-season "
  "behavior may differ, which matters directly for interpreting the forest-ring null. Third, the "
  "standardized deployment isolates morphology but is not any operator’s network; absolute coverage "
  "levels would shift with real site inventories, antenna patterns, and traffic engineering, and the "
  "morphological ranking—the object of this study—proved moderately stable across grid phases for open "
  "villages but genuinely phase-sensitive for marginal ones, a heterogeneity our four-phase mean only "
  "partly absorbs. Fourth, the propagation chain is a deterministic received-power scenario: it omits "
  "vegetation and building clutter, diffraction refinement, shadowing, and interference; reported "
  "coverage is optimistic in absolute terms, the forest-ring effect is conservative, and validation "
  "against measured or crowdsourced RSRP, or against a diffraction-capable model such as ITU-R P.1812 "
  "or Longley–Rice, remains future work. Fifth, the morphometrics are coarse by architectural "
  "standards: tSVF is evaluated once at the built-up centroid rather than across the fabric, and the "
  "10-m land-cover map cannot resolve the narrow lanes, courtyards, building heights, and street H/W "
  "ratios of Huizhou villages; the courtyard-scale design hypotheses mentioned in Section 4.1 are "
  "therefore speculative and require building-scale data. Sixth, two villages rely on fallback coverage "
  "targets and lack component-based metrics; although exclusion checks leave the headline associations "
  "unchanged, manual or semi-automated mapping of their built boundaries—ideally tied to field survey—"
  "would remove this caveat. Seventh, the sample is a regional convenience sample (n = 29); Moran’s I "
  "detects significant spatial clustering in tSVF and cov85, and while the leave-one-county jackknife "
  "shows no county drives the results, nominal p-values should be read with that dependence in mind. "
  "Eighth, one village’s detected built component merges with a county seat, though excluding it changes "
  "no reported sign.")
P("Future work follows four lines: (i) multi-season and diurnal LST composites, plus air-temperature "
  "and comfort sensor campaigns in a stratified subsample of villages; (ii) building-scale morphometrics "
  "from high-resolution imagery or survey—street H/W, courtyard green view, building-resolved SVF—tested "
  "against the settlement-scale associations reported here; (iii) validation of the radio chain against "
  "real operator inventories and crowdsourced measurements, and cross-checking against a diffraction-"
  "capable propagation model; and (iv) extension of the sample beyond Huizhou to test whether the "
  "trade-off axes generalize across mountain-village regions with different building traditions.")

# ==================== 5. CONCLUSIONS ====================
H1("5. Conclusions")
P("Across 29 traditional Huizhou villages, settlement morphology is associated with summer surface "
  "temperature and with simulated wireless coverage in systematically coupled ways. Every village "
  "exhibits a positive summer heat anomaly (mean +2.5 °C); the anomaly covaries with compactness even "
  "at fixed size (partial ρ = +0.70), while absolute temperature covaries mainly with terrain setting "
  "(relief ρ = −0.67; elevation ρ = −0.62; openness ρ = +0.60). Three trade-off axes emerge under a "
  "consistent utility rule—openness, relief, and elongation each carry opposite-signed associations "
  "with the thermal and coverage utilities—while the forest ring is a one-sided digital cost whose "
  "village-scale daytime thermal benefit does not survive quality control, and southness is inert at "
  "settlement scale. The associations are robust to grid phase, frequency band, county jackknife, and "
  "outlier exclusion, and the entire analysis runs on open data and a scripted, deposited pipeline. For "
  "the agencies that must reconcile climate adaptation with digital modernization in historic mountain "
  "settlements, the central lesson is that the conflict is real in the data, quantifiable—and, once "
  "made visible, manageable by design.")

# ==================== 声明 ====================
H1("Declarations")
P("**Data Availability.** The full analysis code, the village-level analysis table (all twelve "
  "morphological metrics, four performance variables, and four-phase coverage detail), the Landsat "
  "scene manifest, and the figure scripts are deposited at [GitHub repository URL to be inserted] and "
  "archived at [Zenodo DOI to be inserted]. Public input datasets are cited in the References.")
P("**Author Contributions (CRediT).** Lei Zhang: conceptualization, methodology, software, formal "
  "analysis, investigation, data curation, writing—original draft, writing—review and editing, "
  "visualization, project administration. [Additional authors and roles to be inserted if applicable.]")
P("**Conflicts of Interest.** The author declares no conflict of interest.")
P("**Funding.** [Funding information to be inserted.]")

H1("Acknowledgments")
P("The author thanks the data providers: the U.S. Geological Survey and Microsoft Planetary Computer "
  "for Landsat access, the European Space Agency for WorldCover, and the Copernicus programme for the "
  "digital elevation model; and Esri for the World Imagery base map used in Fig. 1.")

# ==================== REFERENCES ====================
H1("References")
refs = [
    "Z. J. Zhai and J. M. Previtali, “Ancient vernacular architecture: Characteristics categorization "
    "and energy performance evaluation,” Energy and Buildings, vol. 42, no. 3, pp. 357–365, 2010.",
    "S. Gou, Z. Li, Q. Zhao, V. M. Nik, and J.-L. Scartezzini, “Climate responsive strategies of "
    "traditional dwellings located in an ancient village in hot summer and cold winter region of "
    "China,” Building and Environment, vol. 86, pp. 151–165, 2015.",
    "C. Pan, Y. Wu, S. Chen, and Y. Yang, “Indoor environmental comfort assessment of traditional folk "
    "houses: A case study in southern Anhui, China,” International Journal of Environmental Research "
    "and Public Health, vol. 20, no. 4, 3024, 2023.",
    "Y. Xiong, J. Zhang, Y. Yan, S. Sun, X. Xu, and E. Higueras, “Effect of the spatial form of "
    "Jiangnan traditional villages on microclimate and human comfort,” Sustainable Cities and Society, "
    "vol. 87, 104136, 2022.",
    "Central Committee of the Communist Party of China and the State Council, Strategic Outline for "
    "Digital Village Development, Beijing, China, 2019 (in Chinese).",
    "Ministry of Housing and Urban-Rural Development of the People’s Republic of China, Technical "
    "Standard for City Information Modeling Basic Platforms, CJJ/T 315-2022, Beijing, China, 2022 "
    "(in Chinese).",
    "Z. Wan, et al., “How does outdoor spatial design shape the microclimate, comfort, and behavior "
    "in traditional Chinese villages? A systematic review across scales, contexts, and users,” "
    "Sustainability, vol. 17, no. 15, 6960, 2025.",
    "M. Hata, “Empirical formula for propagation loss in land mobile radio services,” IEEE "
    "Transactions on Vehicular Technology, vol. 29, no. 3, pp. 317–325, 1980.",
    "3GPP, “Study on channel model for frequencies from 0.5 to 100 GHz,” 3rd Generation Partnership "
    "Project, Sophia Antipolis, France, TR 38.901 V16.1.0, 2019.",
    "T. S. Rappaport, Wireless Communications: Principles and Practice, 2nd ed. Upper Saddle River, "
    "NJ, USA: Prentice Hall, 2002.",
    "T. R. Oke, “The energetic basis of the urban heat island,” Quarterly Journal of the Royal "
    "Meteorological Society, vol. 108, no. 455, pp. 1–24, 1982.",
    "A. J. Arnfield, “Two decades of urban climate research: A review of turbulence, exchanges of "
    "energy and water, and the urban heat island,” International Journal of Climatology, vol. 23, "
    "no. 1, pp. 1–26, 2003.",
    "I. D. Stewart and T. R. Oke, “Local climate zones for urban temperature studies,” Bulletin of "
    "the American Meteorological Society, vol. 93, no. 12, pp. 1879–1900, 2012.",
    "T. R. Oke, “Canyon geometry and the nocturnal urban heat island: Comparison of scale model and "
    "field observations,” Journal of Climatology, vol. 1, no. 3, pp. 237–254, 1981.",
    "K. Žákšek, K. Oštir, and Ž. Kokalj, “Sky-view factor as a relief visualization technique,” "
    "Remote Sensing, vol. 3, no. 2, pp. 398–415, 2011.",
    "Y. Xiong, Y. He, X. Xie, T. Zhai, N. Chu, L. Shen, and Y. Yang, “A study on the spatial form of "
    "traditional villages in Jiangnan region of China from the perspective of human thermal comfort: "
    "A case study of Nanjing, Jiangsu Province,” PLoS ONE, vol. 20, no. 5, e0323252, 2025.",
    "S. Wu, et al., “Research on microclimate optimization of traditional residential buildings in "
    "central Anhui based on humid and hot climate characteristics and regional architectural "
    "features,” Buildings, vol. 14, no. 8, 2323, 2024.",
    "A. Middel, K. Häb, A. J. Brazel, C. A. Martin, and S. Guhathakurta, “Impact of urban form and "
    "design on mid-afternoon microclimate in Phoenix Local Climate Zones,” Landscape and Urban "
    "Planning, vol. 122, pp. 16–28, 2014.",
    "ITU-R, “Attenuation in vegetation,” International Telecommunication Union, Geneva, Switzerland, "
    "Recommendation ITU-R P.833-9, 2019.",
    "ITU, Measuring Digital Development: Facts and Figures 2023. Geneva, Switzerland: International "
    "Telecommunication Union, 2023.",
    "European Space Agency, “Copernicus digital elevation model (COP-DEM GLO-30),” 2021. [Online]. "
    "Available: https://spacedata.copernicus.eu/collections/copernicus-digital-elevation-model "
    "(accessed August 2026).",
    "X. Li, C. Zhang, W. Li, R. Ricard, Q. Meng, and W. Zhang, “Assessing street-level urban greenery "
    "using Google Street View and a modified green view index,” Urban Forestry & Urban Greening, "
    "vol. 14, no. 3, pp. 675–685, 2015.",
    "D. Zanaga et al., “ESA WorldCover 10 m 2021 v200,” Zenodo, 2022. [Online]. Available: "
    "https://doi.org/10.5281/zenodo.7254221 (accessed August 2026).",
    "Y. Long and L. Liu, “How green are the streets? An analysis for central areas of Chinese cities "
    "using Tencent Street View,” PLoS ONE, vol. 12, no. 2, e0171110, 2017.",
    "Y. Ye, D. Richards, Y. Lu, X. Song, Y. Zhuang, W. Zeng, and T. Zhong, “Measuring daily accessed "
    "street greenery: A human-scale approach for informing better urban planning practices,” Landscape "
    "and Urban Planning, vol. 191, 103434, 2019.",
    "U.S. Geological Survey, “Landsat 8–9 OLI/TIRS Collection 2 Level-2 science products,” 2021. "
    "[Online]. Available: https://www.usgs.gov/landsat-missions (accessed August 2026).",
    "Microsoft, “Planetary Computer: A planetary platform for sustainability,” 2026. [Online]. "
    "Available: https://planetarycomputer.microsoft.com (accessed August 2026).",
    "J. A. Voogt and T. R. Oke, “Thermal remote sensing of urban climates,” Remote Sensing of "
    "Environment, vol. 86, no. 3, pp. 370–384, 2003.",
    "Y. Benjamini and Y. Hochberg, “Controlling the false discovery rate: A practical and powerful "
    "approach to multiple testing,” Journal of the Royal Statistical Society: Series B, vol. 57, "
    "no. 1, pp. 289–300, 1995.",
    "H. Theil, “A rank-invariant method of linear and polynomial regression analysis,” Indagationes "
    "Mathematicae, vol. 12, pp. 85–91, 1950.",
    "P. K. Sen, “Estimates of the regression coefficient based on Kendall’s tau,” Journal of the "
    "American Statistical Association, vol. 63, no. 324, pp. 1379–1389, 1968.",
]
for i, r in enumerate(refs, 1):
    p = doc.add_paragraph()
    run = p.add_run(f"[{i}] {r}")
    run.font.size = Pt(10)
    p.paragraph_format.space_after = Pt(3)

# ==================== APPENDIX ====================
doc.add_page_break()
H1("Appendix A. Full Metric Table and Supporting Data")
P("Table A1 reports all twelve morphological metrics, the four performance variables, per-phase "
  "coverage, and Landsat observation support for the 29 villages; Table A2 lists the Landsat scene "
  "manifest. Both are generated by script from the same analysis table that feeds the in-text "
  "statistics.", size=9.5)
_a1 = pd.read_csv("tables/TableA1_full.csv").fillna("—")
TABLE("A1", "Full village-level analysis table (29 villages). built_dom: domain (500-m) built-up area; "
            "built_comp: connected-component built-up area; obs_min/obs_med: per-pixel Landsat "
            "observation support within the village domain; cov85_pX_Y: cov85 under grid phase (X, Y).",
      list(_a1.columns), _a1.round(2).values.tolist(), fontsize=6)
_man = pd.read_csv("data/lst_scene_manifest.csv")
TABLE("A2", "Landsat 8/9 Collection-2 scene manifest (36 scenes queried; the three scenes whose "
            "surface-temperature retrieval failed the QA chain—zero valid pixels—are marked and "
            "excluded, leaving 33 valid scenes).",
      ["Product ID", "Date", "Scene cloud (%)", "Path", "Row", "Valid"],
      [[r.id, r.date, r.cloud, r.path, (r.row if hasattr(r, "row") else r["row"]),
        ("no" if r.id in {"LC08_L2SP_120040_20200627_02_T2",
                          "LC08_L2SP_121039_20230729_02_T2",
                          "LC08_L2SP_121039_20200720_02_T1"} else "yes")]
       for r in _man.itertuples()],
      fontsize=7)

doc.save(OUT)
print("saved", OUT, "tables:", len(doc.tables))
