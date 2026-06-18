from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, text
from sqlalchemy.orm import load_only
from app.database import get_db
from app.models.lead import Lead
from typing import Optional
from datetime import datetime, timedelta
import io
import pandas as pd
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.legends import Legend

router = APIRouter()


@router.get("/stats")
async def get_leads_stats(db: AsyncSession = Depends(get_db)):
    """KPIs dashboard : totaux, segments, taux email, score moyen"""
    result = await db.execute(
        select(
            func.count(Lead.id).label("total"),
            func.count(case((Lead.email != None, 1))).label("with_email"),
            func.count(case((Lead.phone != None, 1))).label("with_phone"),
            func.count(case((Lead.website != None, 1))).label("with_website"),
            func.count(case((Lead.sector != None, 1))).label("with_sector"),
            func.count(case((Lead.region != None, 1))).label("with_region"),
            func.count(case((Lead.description != None, 1))).label("with_desc"),
            func.count(case((Lead.company_type != None, 1))).label("with_type"),
            func.avg(Lead.lead_score).label("avg_score"),
            func.count(case((Lead.segment == "Chaud", 1))).label("chaud"),
            func.count(case((Lead.segment == "Prêts à Acheter", 1))).label("tiede"),
            func.count(case((Lead.segment == "Froid", 1))).label("froid"),
            func.count(case((Lead.segment == "À Risque", 1))).label("a_risque"),
            func.count(case((Lead.enriched == True, 1))).label("enriched"),
        )
    )
    row = result.one()

    # Distribution par secteur (top 8)
    sector_result = await db.execute(
        select(Lead.sector, func.count(Lead.id).label("count"))
        .where(Lead.sector != None)
        .group_by(Lead.sector)
        .order_by(func.count(Lead.id).desc())
        .limit(8)
    )
    sectors = [{"sector": r.sector, "count": r.count} for r in sector_result]

    # Distribution par source
    source_result = await db.execute(
        select(Lead.source, func.count(Lead.id).label("count"))
        .where(Lead.source != None)
        .group_by(Lead.source)
        .order_by(func.count(Lead.id).desc())
    )
    sources = [{"source": r.source, "count": r.count} for r in source_result]

    # Leads ajoutés par semaine (12 dernières semaines)
    week_result = await db.execute(text("""
        SELECT
            DATE_TRUNC('week', created_at) AS week_start,
            COUNT(*) AS count
        FROM leads
        WHERE created_at >= NOW() - INTERVAL '12 weeks'
        GROUP BY week_start
        ORDER BY week_start
    """))
    leads_per_week = [
        {"week": r.week_start.strftime("%d/%m"), "count": r.count}
        for r in week_result
    ]

    # Leads "à re-scraper" : scraped_at > 6 mois ou jamais scrapés et créé > 6 mois
    stale_cutoff = datetime.utcnow() - timedelta(days=180)
    stale_result = await db.execute(
        select(func.count(Lead.id)).where(
            (Lead.scraped_at < stale_cutoff) | (Lead.scraped_at == None)
        ).where(Lead.created_at < stale_cutoff)
    )
    stale_count = stale_result.scalar() or 0

    # KPIs temporels : aujourd'hui / semaine / mois
    time_result = await db.execute(text("""
        SELECT
            COUNT(*) FILTER (WHERE scraped_at >= NOW() - INTERVAL '1 day')   AS today,
            COUNT(*) FILTER (WHERE scraped_at >= NOW() - INTERVAL '7 days')  AS this_week,
            COUNT(*) FILTER (WHERE scraped_at >= NOW() - INTERVAL '30 days') AS this_month
        FROM leads
    """))
    time_row = time_result.one()

    # Taux de conversion par source (email_sent / total)
    conv_result = await db.execute(text("""
        SELECT
            source,
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE email_sent = true) as contacted,
            COUNT(*) FILTER (WHERE email_opened = true) as opened,
            ROUND(COUNT(*) FILTER (WHERE email_sent = true)::numeric / NULLIF(COUNT(*),0) * 100, 1) as contact_rate,
            ROUND(COUNT(*) FILTER (WHERE email_opened = true)::numeric / NULLIF(COUNT(*) FILTER (WHERE email_sent = true),0) * 100, 1) as open_rate
        FROM leads
        WHERE source IS NOT NULL
        GROUP BY source
        ORDER BY total DESC
    """))
    sources_conversion = [
        {
            "source": r.source,
            "total": r.total,
            "contacted": r.contacted,
            "opened": r.opened,
            "contact_rate": float(r.contact_rate or 0),
            "open_rate": float(r.open_rate or 0),
        }
        for r in conv_result
    ]

    # Statut des leads
    status_result = await db.execute(text("""
        SELECT status, COUNT(*) as count FROM leads GROUP BY status ORDER BY count DESC
    """))
    status_dist = [{"status": r.status, "count": r.count} for r in status_result]

    total = row.total or 1
    return {
        "total": row.total,
        "with_email":   row.with_email,
        "with_phone":   row.with_phone,
        "with_website": row.with_website,
        "email_rate":   round((row.with_email / total) * 100, 1),
        "avg_score":    round(float(row.avg_score or 0), 1),
        "enriched":     row.enriched,
        "segments": {
            "Chaud":           row.chaud,
            "Prêts à Acheter": row.tiede,
            "Froid":           row.froid,
            "A Risque":        row.a_risque,
        },
        "enrichment_coverage": [
            {"field": "Téléphone",    "count": row.with_phone,   "rate": round(row.with_phone   / total * 100, 1)},
            {"field": "Description",  "count": row.with_desc,    "rate": round(row.with_desc    / total * 100, 1)},
            {"field": "Région",       "count": row.with_region,  "rate": round(row.with_region  / total * 100, 1)},
            {"field": "Site web",     "count": row.with_website, "rate": round(row.with_website / total * 100, 1)},
            {"field": "Email",        "count": row.with_email,   "rate": round(row.with_email   / total * 100, 1)},
            {"field": "Type société", "count": row.with_type,    "rate": round(row.with_type    / total * 100, 1)},
            {"field": "Secteur",      "count": row.with_sector,  "rate": round(row.with_sector  / total * 100, 1)},
        ],
        "sectors": sectors,
        "sources": sources,
        "leads_per_week": leads_per_week,
        "stale_leads": stale_count,
        "scraped_today":    int(time_row.today or 0),
        "scraped_week":     int(time_row.this_week or 0),
        "scraped_month":    int(time_row.this_month or 0),
        "sources_conversion": sources_conversion,
        "status_distribution": status_dist,
    }


@router.get("/export/excel")
async def export_leads_excel(db: AsyncSession = Depends(get_db)):
    """Export de tous les leads au format Excel (.xlsx)"""
    result = await db.execute(
        select(Lead).order_by(Lead.lead_score.desc().nullslast()).limit(10000)
    )
    leads = result.scalars().all()

    rows = []
    for l in leads:
        rows.append({
            "ID": l.id,
            "Entreprise": l.company or "",
            "Prénom": l.first_name or "",
            "Nom": l.last_name or "",
            "Email": l.email or "",
            "Téléphone": l.phone or "",
            "Site Web": l.website or "",
            "Secteur": l.sector or "",
            "Région": l.region or "",
            "Adresse": l.address or "",
            "Description": (l.description or "")[:100],
            "Score IA": round(l.lead_score or 0, 1),
            "Segment": l.segment or "",
            "Statut": l.status or "",
            "Source": l.source or "",
            "Enrichi": "Oui" if l.enriched else "Non",
            "Email envoyé": "Oui" if l.email_sent else "Non",
            "Email ouvert": "Oui" if l.email_opened else "Non",
            "Date création": l.created_at.strftime("%d/%m/%Y %H:%M") if l.created_at else "",
        })

    df = pd.DataFrame(rows)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Leads")
        ws = writer.sheets["Leads"]
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 40)
    buffer.seek(0)

    filename = f"leads_leadpilot_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/pdf")
async def export_leads_pdf(db: AsyncSession = Depends(get_db)):
    """Export des 500 meilleurs leads au format PDF"""
    result = await db.execute(
        select(Lead).order_by(Lead.lead_score.desc().nullslast()).limit(500)
    )
    leads = result.scalars().all()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=1*cm, rightMargin=1*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
    )

    styles = getSampleStyleSheet()
    blue = colors.HexColor("#3b82f6")
    lightblue = colors.HexColor("#eff6ff")

    title_style = ParagraphStyle("title", fontSize=16, fontName="Helvetica-Bold",
                                  textColor=blue, alignment=TA_CENTER, spaceAfter=4)
    sub_style   = ParagraphStyle("sub",   fontSize=9,  fontName="Helvetica",
                                  textColor=colors.gray, alignment=TA_CENTER, spaceAfter=12)

    elements = [
        Paragraph("LeadPilot — Export Leads", title_style),
        Paragraph(f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')} · {len(leads)} leads (top par score IA)", sub_style),
        Spacer(1, 0.3*cm),
    ]

    headers = ["#", "Entreprise", "Email", "Téléphone", "Secteur", "Région", "Score IA", "Segment", "Statut", "Source"]
    col_widths = [1*cm, 4.5*cm, 5*cm, 3.5*cm, 3.5*cm, 3*cm, 2.2*cm, 3*cm, 2.5*cm, 3*cm]

    data = [headers]
    seg_colors = {
        "Chaud": colors.HexColor("#fef2f2"),
        "Prêts à Acheter": colors.HexColor("#fff7ed"),
        "Froid": colors.HexColor("#eff6ff"),
        "À Risque": colors.HexColor("#fffbeb"),
    }
    row_seg = []
    for l in leads:
        data.append([
            str(l.id),
            (l.company or "—")[:35],
            (l.email or "—")[:35],
            l.phone or "—",
            (l.sector or "—")[:25],
            (l.region or "—")[:20],
            f"{round(l.lead_score or 0, 1)}/100",
            l.segment or "—",
            l.status or "—",
            (l.source or "—").replace("_", " "),
        ])
        row_seg.append(l.segment or "")

    ts = TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0),  blue),
        ("TEXTCOLOR",    (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, 0),  8),
        ("ALIGN",        (0, 0), (-1, -1), "LEFT"),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME",     (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",     (0, 1), (-1, -1), 7),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("GRID",         (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("LEFTPADDING",  (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ])
    for i, seg in enumerate(row_seg, start=1):
        bg = seg_colors.get(seg)
        if bg:
            ts.add("BACKGROUND", (7, i), (7, i), bg)

    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(ts)
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)

    filename = f"leads_leadpilot_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


PALETTE = ["#6366f1", "#0ea5e9", "#10b981", "#f59e0b", "#e11d48", "#7c3aed", "#f97316", "#64748b"]


def _make_pie(data_pairs, width=240, height=170):
    d = Drawing(width, height)
    pie = Pie()
    pie.x = 10
    pie.y = 10
    pie.width = 130
    pie.height = 130
    pie.data = [v for _, v in data_pairs] or [1]
    pie.labels = None
    pie.slices.strokeWidth = 0.5
    pie.slices.strokeColor = colors.white
    for i in range(len(data_pairs)):
        pie.slices[i].fillColor = colors.HexColor(PALETTE[i % len(PALETTE)])
    d.add(pie)

    legend = Legend()
    legend.x = 155
    legend.y = height - 30
    legend.dx = 7
    legend.dy = 7
    legend.fontName = "Helvetica"
    legend.fontSize = 8
    legend.alignment = "right"
    legend.columnMaximum = 6
    legend.colorNamePairs = [
        (colors.HexColor(PALETTE[i % len(PALETTE)]), f"{name} ({val})")
        for i, (name, val) in enumerate(data_pairs)
    ]
    d.add(legend)
    return d


def _make_bar(categories, series_dict, width=480, height=200):
    d = Drawing(width, height)
    chart = VerticalBarChart()
    chart.x = 35
    chart.y = 30
    chart.width = width - 120
    chart.height = height - 60
    chart.data = list(series_dict.values())
    chart.categoryAxis.categoryNames = categories
    chart.categoryAxis.labels.fontName = "Helvetica"
    chart.categoryAxis.labels.fontSize = 8
    chart.categoryAxis.labels.angle = 0
    chart.valueAxis.valueMin = 0
    chart.barWidth = 5
    chart.groupSpacing = 12
    chart.valueAxis.labels.fontName = "Helvetica"
    chart.valueAxis.labels.fontSize = 7
    for i in range(len(series_dict)):
        chart.bars[i].fillColor = colors.HexColor(PALETTE[i % len(PALETTE)])
    d.add(chart)

    legend = Legend()
    legend.x = width - 75
    legend.y = height - 25
    legend.dx = 7
    legend.dy = 7
    legend.fontName = "Helvetica"
    legend.fontSize = 8
    legend.colorNamePairs = [
        (colors.HexColor(PALETTE[i % len(PALETTE)]), name)
        for i, name in enumerate(series_dict.keys())
    ]
    d.add(legend)
    return d


@router.get("/export/report-pdf")
async def export_analytics_report(db: AsyncSession = Depends(get_db)):
    """Rapport analytique complet (page de garde, KPIs, graphiques) généré côté serveur."""
    # Statistiques globales 
    total      = (await db.execute(select(func.count(Lead.id)))).scalar() or 0
    with_email = (await db.execute(select(func.count(Lead.id)).where(Lead.email != None))).scalar() or 0
    enriched   = (await db.execute(select(func.count(Lead.id)).where(Lead.enriched == True))).scalar() or 0
    scored     = (await db.execute(select(func.count(Lead.id)).where(Lead.lead_score != None))).scalar() or 0

    seg_rows = (await db.execute(
        select(Lead.segment, func.count(Lead.id)).where(Lead.segment != None).group_by(Lead.segment)
    )).all()
    segments = [(s or "Non segmenté", c) for s, c in seg_rows]

    sect_rows = (await db.execute(
        select(Lead.sector, func.count(Lead.id))
        .where(Lead.sector != None).group_by(Lead.sector)
        .order_by(func.count(Lead.id).desc()).limit(8)
    )).all()

    sent    = (await db.execute(select(func.count(Lead.id)).where(Lead.email_sent == True))).scalar() or 0
    opened  = (await db.execute(select(func.count(Lead.id)).where(Lead.email_opened == True))).scalar() or 0
    clicked = (await db.execute(select(func.count(Lead.id)).where(Lead.email_clicked == True))).scalar() or 0
    open_rate  = round(opened / sent * 100, 1) if sent else 0
    click_rate = round(clicked / sent * 100, 1) if sent else 0

    eng_rows = (await db.execute(
        select(
            Lead.segment,
            func.count(case((Lead.email_sent == True, 1))),
            func.count(case((Lead.email_opened == True, 1))),
            func.count(case((Lead.email_clicked == True, 1))),
        ).where(Lead.email_sent == True).group_by(Lead.segment)
    )).all()

    # Construction du document 
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    indigo = colors.HexColor("#6366f1")
    dark   = colors.HexColor("#1e293b")
    gray   = colors.HexColor("#64748b")

    h1 = ParagraphStyle("h1", fontSize=26, fontName="Helvetica-Bold", textColor=dark, alignment=TA_CENTER, leading=30)
    h2 = ParagraphStyle("h2", fontSize=14, fontName="Helvetica-Bold", textColor=indigo, spaceBefore=14, spaceAfter=8)
    sub = ParagraphStyle("sub", fontSize=11, fontName="Helvetica", textColor=gray, alignment=TA_CENTER, spaceAfter=4)
    body = ParagraphStyle("body", fontSize=10, fontName="Helvetica", textColor=dark, alignment=TA_LEFT)

    el = []

    # PAGE DE GARDE 
    el.append(Spacer(1, 5*cm))
    el.append(Paragraph("LeadPilot", h1))
    el.append(Spacer(1, 0.4*cm))
    el.append(Paragraph("Rapport Analytique", ParagraphStyle("t2", fontSize=18, fontName="Helvetica", textColor=indigo, alignment=TA_CENTER)))
    el.append(Spacer(1, 0.8*cm))
    el.append(Paragraph(f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}", sub))
    el.append(Spacer(1, 1.5*cm))
    cover = Table([
        ["Total leads", "Avec email", "Enrichis", "Emails envoyés"],
        [str(total), str(with_email), str(enriched), str(sent)],
    ], colWidths=[4*cm]*4)
    cover.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("TEXTCOLOR", (0, 0), (-1, 0), gray),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, 1), 20),
        ("TEXTCOLOR", (0, 1), (-1, 1), indigo),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    el.append(cover)
    el.append(PageBreak())

    # SECTION 1 : KPIs leads 
    el.append(Paragraph("1. Vue d'ensemble des leads", h2))
    enrich_rate = round(enriched / total * 100, 1) if total else 0
    score_rate  = round(scored / total * 100, 1) if total else 0
    kpi_tbl = Table([
        ["Indicateur", "Valeur"],
        ["Total leads", str(total)],
        ["Leads avec email", f"{with_email} ({round(with_email/total*100,1) if total else 0}%)"],
        ["Leads enrichis (IA)", f"{enriched} ({enrich_rate}%)"],
        ["Leads scorés (XGBoost)", f"{scored} ({score_rate}%)"],
    ], colWidths=[9*cm, 6*cm])
    kpi_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), indigo),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    el.append(kpi_tbl)

    # SECTION 2 : segments (camembert) 
    if segments:
        el.append(Paragraph("2. Répartition par segment", h2))
        el.append(_make_pie(segments))

    # SECTION 3 : Marketing 
    el.append(Paragraph("3. Performance Marketing", h2))
    mk_tbl = Table([
        ["Emails envoyés", "Taux d'ouverture", "Taux de clic"],
        [str(sent), f"{open_rate}%", f"{click_rate}%"],
    ], colWidths=[5*cm]*3)
    mk_tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("TEXTCOLOR", (0, 0), (-1, 0), gray),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, 1), 18),
        ("TEXTCOLOR", (0, 1), (-1, 1), indigo),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("BOX", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
    ]))
    el.append(mk_tbl)

    if eng_rows:
        el.append(Spacer(1, 0.4*cm))
        cats = [(r[0] or "—") for r in eng_rows]
        el.append(_make_bar(cats, {
            "Envoyés": [r[1] for r in eng_rows],
            "Ouverts": [r[2] for r in eng_rows],
            "Cliqués": [r[3] for r in eng_rows],
        }))

    # SECTION 4 : top secteurs 
    if sect_rows:
        el.append(Paragraph("4. Top secteurs", h2))
        st_data = [["Secteur", "Nombre de leads"]] + [[(s or "—")[:40], str(c)] for s, c in sect_rows]
        st_tbl = Table(st_data, colWidths=[10*cm, 5*cm])
        st_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), indigo),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        el.append(st_tbl)

    doc.build(el)
    buffer.seek(0)
    filename = f"rapport_leadpilot_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/feature-importance")
async def get_feature_importance():
    """Retourne l'importance des features XGBoost pour le Dashboard."""
    from app.scoring import get_feature_importance as _get_fi
    return {"features": _get_fi()}


@router.get("/")
async def get_leads(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None),
    segment: Optional[str] = Query(None),
    sector: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    has_email: Optional[bool] = Query(None),
    source: Optional[str] = Query(None),
):
    """Liste paginée avec filtres"""
    query = select(Lead)
    count_query = select(func.count(Lead.id))

    if search:
        like = f"%{search}%"
        query = query.where(
            Lead.company.ilike(like) |
            Lead.email.ilike(like) |
            Lead.phone.ilike(like) |
            Lead.first_name.ilike(like) |
            Lead.last_name.ilike(like)
        )
        count_query = count_query.where(
            Lead.company.ilike(like) |
            Lead.email.ilike(like) |
            Lead.phone.ilike(like) |
            Lead.first_name.ilike(like) |
            Lead.last_name.ilike(like)
        )

    if segment:
        query = query.where(Lead.segment == segment)
        count_query = count_query.where(Lead.segment == segment)

    if sector:
        query = query.where(Lead.sector == sector)
        count_query = count_query.where(Lead.sector == sector)

    if status:
        query = query.where(Lead.status == status)
        count_query = count_query.where(Lead.status == status)

    if has_email is not None:
        if has_email:
            query = query.where(Lead.email != None)
            count_query = count_query.where(Lead.email != None)
        else:
            query = query.where(Lead.email == None)
            count_query = count_query.where(Lead.email == None)

    if source:
        query = query.where(Lead.source == source)
        count_query = count_query.where(Lead.source == source)

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    offset = (page - 1) * limit
    query = query.order_by(Lead.lead_score.desc().nullslast(), Lead.id.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    leads = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
        "items": leads,
    }


@router.get("/{id}")
async def get_lead(id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Lead).where(Lead.id == id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead non trouvé")
    return lead


@router.put("/{id}/status")
async def update_lead_status(id: int, data: dict, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Lead).where(Lead.id == id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead non trouvé")
    if "status" in data:
        lead.status = data["status"]
    await db.commit()
    await db.refresh(lead)
    return lead


@router.post("/")
async def create_lead(data: dict, db: AsyncSession = Depends(get_db)):
    lead = Lead(**data)
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    return lead


@router.delete("/{id}")
async def delete_lead(id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Lead).where(Lead.id == id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead introuvable")
    await db.delete(lead)
    await db.commit()
    return {"success": True}
