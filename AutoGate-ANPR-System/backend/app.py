from datetime import datetime
from io import BytesIO

from flask import Flask, render_template, request, jsonify, send_file
import os
import sys
from database.db import get_all_records, search_records, create_table, get_dashboard_stats

# Get the absolute path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(os.path.dirname(BASE_DIR), 'frontend')

app = Flask(__name__,
            template_folder=os.path.join(FRONTEND_DIR, 'templates'),
            static_folder=os.path.join(FRONTEND_DIR, 'static'),
            static_url_path='/static')

create_table()


def image_url(filename):
    if not filename:
        return None
    return f"/static/images/{os.path.basename(filename)}"


def serialize_record(record):
    return {
        'id': record[0],
        'plate': record[1],
        'entry_time': record[2],
        'exit_time': record[3] or 'Still Inside',
        'duration': record[4] or 'N/A',
        'entry_image': os.path.basename(record[5]) if record[5] else None,
        'exit_image': os.path.basename(record[6]) if record[6] else None,
        'entry_image_url': image_url(record[5]),
        'exit_image_url': image_url(record[6])
    }

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/search')
def search():
    return render_template('search.html')

@app.route('/api/vehicles')
def get_vehicles():
    records = get_all_records()
    return jsonify([serialize_record(record) for record in records])


@app.route('/api/stats')
def stats():
    return jsonify(get_dashboard_stats())

@app.route('/api/search')
def search_vehicle():
    plate = request.args.get('plate', '')
    if not plate:
        return jsonify([])
    records = search_records(plate)
    return jsonify([serialize_record(record) for record in records])


@app.route('/api/export/pdf')
def export_pdf():
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    except ImportError:
        return export_basic_pdf()

    records = get_all_records()
    stats_data = get_dashboard_stats()
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=24, leftMargin=24)
    styles = getSampleStyleSheet()

    elements = [
        Paragraph("University Vehicle Entry/Exit Report", styles["Title"]),
        Paragraph(datetime.now().strftime("Generated on %Y-%m-%d %H:%M:%S"), styles["Normal"]),
        Spacer(1, 12),
        Paragraph(
            "Entries: {total_entries} | Exits: {total_exits} | Inside: {currently_inside} | Unique vehicles: {unique_vehicles}".format(**stats_data),
            styles["Normal"],
        ),
        Spacer(1, 12),
    ]

    table_data = [["Plate", "Entry Time", "Exit Time", "Duration"]]
    for record in records:
        table_data.append([
            record[1],
            record[2],
            record[3] or "Still Inside",
            record[4] or "N/A",
        ])

    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f7fb")]),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(table)
    doc.build(elements)

    buffer.seek(0)
    filename = f"vehicle_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/pdf")


def _pdf_escape(text):
    return str(text).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_basic_pdf(lines):
    page_width = 842
    page_height = 595
    max_lines = 34
    pages = [lines[i:i + max_lines] for i in range(0, len(lines), max_lines)] or [[]]
    objects = []
    page_refs = []

    def add_object(content):
        objects.append(content)
        return len(objects)

    catalog_id = add_object("<< /Type /Catalog /Pages 2 0 R >>")
    pages_id = add_object("")
    font_id = add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    for page_lines in pages:
        text_commands = ["BT", "/F1 10 Tf", "36 550 Td", "14 TL"]
        for line in page_lines:
            text_commands.append(f"({_pdf_escape(line[:130])}) Tj")
            text_commands.append("T*")
        text_commands.append("ET")
        stream = "\n".join(text_commands)
        stream_id = add_object(f"<< /Length {len(stream.encode('latin-1', errors='replace'))} >>\nstream\n{stream}\nendstream")
        page_id = add_object(
            f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {page_width} {page_height}] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {stream_id} 0 R >>"
        )
        page_refs.append(f"{page_id} 0 R")

    objects[pages_id - 1] = f"<< /Type /Pages /Kids [{' '.join(page_refs)}] /Count {len(page_refs)} >>"

    output = BytesIO()
    output.write(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(output.tell())
        output.write(f"{index} 0 obj\n{obj}\nendobj\n".encode("latin-1", errors="replace"))

    xref_offset = output.tell()
    output.write(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.write(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    output.seek(0)
    return output


def export_basic_pdf():
    records = get_all_records()
    stats_data = get_dashboard_stats()
    lines = [
        "University Vehicle Entry/Exit Report",
        datetime.now().strftime("Generated on %Y-%m-%d %H:%M:%S"),
        "Entries: {total_entries} | Exits: {total_exits} | Inside: {currently_inside} | Unique vehicles: {unique_vehicles}".format(**stats_data),
        "",
        "Plate          Entry Time           Exit Time            Duration",
        "-" * 78,
    ]

    for record in records:
        lines.append(
            f"{record[1]:<14} {record[2]:<20} {(record[3] or 'Still Inside'):<20} {record[4] or 'N/A'}"
        )

    buffer = _build_basic_pdf(lines)
    filename = f"vehicle_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/pdf")

if __name__ == '__main__':
    debug = os.environ.get("FLASK_DEBUG") == "1"
    app.run(debug=debug, host='0.0.0.0', port=5000)
