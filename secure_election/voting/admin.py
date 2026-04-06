import csv
import hashlib
from collections import Counter

from django.contrib import admin
from django.http import HttpResponse
from django.utils import timezone
from django.utils.html import format_html

from elections.models import Candidate, Election
from secure_election.utils.encryption import decrypt_vote
from users.models import Voter

from .models import Vote


def _escape_pdf_text(value):
    return (
        str(value)
        .replace('\\', '\\\\')
        .replace('(', '\\(')
        .replace(')', '\\)')
    )


def _pdf_rgb(*components):
    return ' '.join(f'{component:.3f}' for component in components)


def _pdf_rect(x, y, width, height, *, fill=None, stroke=None, line_width=1):
    commands = ['q', f'{line_width} w']
    if fill:
        commands.append(f'{_pdf_rgb(*fill)} rg')
    if stroke:
        commands.append(f'{_pdf_rgb(*stroke)} RG')
    commands.append(f'{x:.2f} {y:.2f} {width:.2f} {height:.2f} re')

    if fill and stroke:
        commands.append('B')
    elif fill:
        commands.append('f')
    else:
        commands.append('S')

    commands.append('Q')
    return commands


def _pdf_line(x1, y1, x2, y2, *, color=(0.75, 0.79, 0.84), line_width=1):
    return [
        'q',
        f'{line_width} w',
        f'{_pdf_rgb(*color)} RG',
        f'{x1:.2f} {y1:.2f} m',
        f'{x2:.2f} {y2:.2f} l',
        'S',
        'Q',
    ]


def _pdf_text(x, y, text, *, font='F1', size=12, color=(0.15, 0.17, 0.20)):
    return [
        'BT',
        f'/{font} {size} Tf',
        f'{_pdf_rgb(*color)} rg',
        f'1 0 0 1 {x:.2f} {y:.2f} Tm',
        f'({_escape_pdf_text(text)}) Tj',
        'ET',
    ]


def _wrap_pdf_text(text, max_chars):
    words = str(text).split()
    if not words:
        return ['']

    lines = []
    current = words[0]

    for word in words[1:]:
        candidate = f'{current} {word}'
        if len(candidate) <= max_chars:
            current = candidate
        else:
            lines.append(current)
            current = word

    lines.append(current)
    return lines


def _bar_color(index):
    palette = [
        (0.10, 0.42, 0.35),
        (0.83, 0.64, 0.25),
        (0.25, 0.46, 0.73),
        (0.69, 0.36, 0.29),
        (0.42, 0.38, 0.66),
    ]
    return palette[index % len(palette)]


def _resolve_report_election(rows):
    election_id = None
    for row in rows:
        if row.get('election_id'):
            election_id = row['election_id']
            break

    if election_id:
        return Election.objects.filter(id=election_id).first()

    return Election.objects.filter(is_active=True).order_by('start_time').first()


def _request_username(request):
    username = getattr(getattr(request, 'user', None), 'username', '') or ''
    return username or 'system'


def _build_report_summary(rows, total_votes, winner, generated_at, election, generated_by, is_tie=False, tied_candidates=None):
    election_name = election.name if election else 'All Elections'
    tied_candidates = tied_candidates or []
    if is_tie and tied_candidates:
        winner_name = f"Tie: {', '.join(tied_candidates)}"
    else:
        winner_name = winner['name'] if winner else 'No result yet'
    payload = '|'.join(
        [
            election_name,
            str(total_votes),
            winner_name,
            generated_at.isoformat(),
            generated_by,
            ','.join(f"{row['name']}:{row['votes']}" for row in rows),
        ]
    )
    digest = hashlib.sha256(payload.encode('utf-8')).hexdigest()
    return {
        'payload': payload,
        'digest': digest,
        'short_digest': digest[:16].upper(),
    }


def _collect_results():
    votes = Vote.objects.select_related('candidate__election').all()
    decrypted_ids = []

    for vote in votes:
        try:
            cid = decrypt_vote(vote.encrypted_candidate)
            decrypted_ids.append(int(cid))
        except Exception:
            continue

    counts = Counter(decrypted_ids)
    candidates = Candidate.objects.select_related('election').in_bulk(counts.keys())
    rows = []

    for candidate_id, total in counts.items():
        candidate = candidates.get(candidate_id)
        if candidate:
            rows.append(
                {
                    'name': candidate.name,
                    'party': candidate.party,
                    'votes': total,
                    'election_id': candidate.election_id,
                }
            )

    rows.sort(key=lambda item: (-item['votes'], item['name'].lower()))
    total_votes = sum(item['votes'] for item in rows)
    for row in rows:
        row['percentage'] = (row['votes'] / total_votes * 100) if total_votes else 0

    winner = None
    is_tie = False
    tied_candidates = []

    if rows:
        top_vote_total = rows[0]['votes']
        top_rows = [row for row in rows if row['votes'] == top_vote_total]
        if len(top_rows) == 1:
            winner = top_rows[0]
        else:
            is_tie = True
            tied_candidates = [row['name'] for row in top_rows]

    election = _resolve_report_election(rows)
    registered_voters = Voter.objects.count()
    turnout = (total_votes / registered_voters * 100) if registered_voters else 0
    generated_at = timezone.localtime()
    report_summary = _build_report_summary(
        rows=rows,
        total_votes=total_votes,
        winner=winner,
        generated_at=generated_at,
        election=election,
        generated_by='system',
        is_tie=is_tie,
        tied_candidates=tied_candidates,
    )

    return {
        'rows': rows,
        'total_votes': total_votes,
        'winner': winner,
        'is_tie': is_tie,
        'tied_candidates': tied_candidates,
        'election': election,
        'registered_voters': registered_voters,
        'turnout': turnout,
        'generated_at': generated_at,
        'report_summary': report_summary,
    }


def _build_chart(commands, rows, x, y, width, height):
    commands.extend(
        _pdf_rect(x, y, width, height, fill=(0.985, 0.989, 0.995), stroke=(0.86, 0.89, 0.93))
    )
    commands.extend(_pdf_text(x + 14, y + height - 18, 'Vote Distribution', font='F2', size=12))

    if not rows:
        commands.extend(_pdf_text(x + 14, y + 18, 'No chart data available.', size=10, color=(0.42, 0.45, 0.50)))
        return

    chart_rows = rows[:4]
    max_votes = max(row['votes'] for row in chart_rows) or 1
    left = x + 88
    bottom = y + 26
    plot_width = width - 108
    plot_height = height - 52
    bar_space = plot_height / len(chart_rows)
    bar_height = min(22, bar_space * 0.55)

    commands.extend(_pdf_line(left, bottom, left, bottom + plot_height, color=(0.78, 0.81, 0.86)))
    commands.extend(_pdf_line(left, bottom, left + plot_width, bottom, color=(0.78, 0.81, 0.86)))

    for index, row in enumerate(chart_rows):
        bar_y = bottom + plot_height - ((index + 1) * bar_space) + ((bar_space - bar_height) / 2)
        bar_width = plot_width * (row['votes'] / max_votes)
        color = _bar_color(index)

        commands.extend(_pdf_text(x + 14, bar_y + 6, row['name'][:14], size=9, color=(0.23, 0.26, 0.31)))
        commands.extend(_pdf_rect(left, bar_y, bar_width, bar_height, fill=color))
        commands.extend(
            _pdf_text(
                left + min(bar_width + 8, plot_width - 50),
                bar_y + 6,
                f"{row['votes']} ({row['percentage']:.1f}%)",
                size=9,
                color=(0.23, 0.26, 0.31),
            )
        )


def _build_results_pdf(report):
    rows = report['rows']
    total_votes = report['total_votes']
    winner = report['winner']
    is_tie = report.get('is_tie', False)
    tied_candidates = report.get('tied_candidates', [])
    election = report['election']
    registered_voters = report['registered_voters']
    turnout = report['turnout']
    generated_at = report['generated_at']
    signature = report['report_summary']['short_digest']
    page_width = 612
    page_height = 792
    margin = 42
    table_header_height = 28
    row_height = 36
    table_width = page_width - (margin * 2)
    rows_per_page = 8
    table_rows = rows or [{'name': 'No votes recorded', 'party': '-', 'votes': 0, 'percentage': 0}]
    generated_label = generated_at.strftime('%d %b %Y, %I:%M %p')
    election_name = election.name if election else 'Election Summary'
    election_status = 'Active' if election and election.is_active else 'Closed'
    winner_label = winner['name'] if winner else 'No result yet'
    leader_heading = 'Leading Candidate'
    if is_tie and tied_candidates:
        winner_label = 'Tie'
        leader_heading = 'Current Status'
    election_period = 'N/A'
    if election:
        election_period = (
            f"{timezone.localtime(election.start_time).strftime('%d %b %Y')} to "
            f"{timezone.localtime(election.end_time).strftime('%d %b %Y')}"
        )

    pages = []
    total_pages = (len(table_rows) + rows_per_page - 1) // rows_per_page

    for page_index in range(total_pages):
        commands = []

        commands.extend(
            _pdf_rect(
                margin,
                page_height - margin - 106,
                table_width,
                106,
                fill=(0.08, 0.24, 0.20),
            )
        )
        commands.extend(
            _pdf_rect(
                margin + 18,
                page_height - margin - 72,
                44,
                44,
                fill=(0.93, 0.74, 0.29),
            )
        )
        commands.extend(
            _pdf_text(
                margin + 29,
                page_height - margin - 50,
                'SES',
                font='F2',
                size=13,
                color=(0.09, 0.17, 0.15),
            )
        )
        commands.extend(
            _pdf_text(
                margin + 76,
                page_height - margin - 34,
                'Election Results Report',
                font='F2',
                size=22,
                color=(1, 1, 1),
            )
        )
        commands.extend(
            _pdf_text(
                margin + 76,
                page_height - margin - 58,
                election_name,
                size=11,
                color=(0.83, 0.94, 0.90),
            )
        )
        commands.extend(
            _pdf_text(
                page_width - margin - 175,
                page_height - margin - 34,
                f'Generated: {generated_label}',
                size=10,
                color=(0.83, 0.94, 0.90),
            )
        )
        commands.extend(
            _pdf_text(
                page_width - margin - 175,
                page_height - margin - 56,
                f'Signed summary: {signature}',
                size=10,
                color=(0.93, 0.74, 0.29),
            )
        )

        meta_top = page_height - margin - 136
        meta_cards = [
            ('Status', election_status, 130, (0.95, 0.98, 0.97), (0.81, 0.88, 0.84)),
            ('Registered', str(registered_voters), 110, (0.97, 0.97, 0.99), (0.84, 0.87, 0.92)),
            ('Votes Cast', str(total_votes), 110, (0.97, 0.96, 0.93), (0.89, 0.84, 0.73)),
            ('Turnout', f'{turnout:.1f}%', 110, (0.94, 0.97, 0.99), (0.80, 0.87, 0.92)),
        ]
        card_x = margin
        for label, value, width, fill, stroke in meta_cards:
            commands.extend(_pdf_rect(card_x, meta_top - 52, width, 52, fill=fill, stroke=stroke))
            commands.extend(_pdf_text(card_x + 12, meta_top - 18, label, size=9, color=(0.34, 0.37, 0.41)))
            commands.extend(_pdf_text(card_x + 12, meta_top - 38, value, font='F2', size=15, color=(0.11, 0.19, 0.18)))
            card_x += width + 10

        commands.extend(
            _pdf_rect(margin, meta_top - 124, table_width, 56, fill=(1, 1, 1), stroke=(0.87, 0.90, 0.93))
        )
        commands.extend(_pdf_text(margin + 14, meta_top - 88, 'Election Period', font='F2', size=10))
        commands.extend(_pdf_text(margin + 14, meta_top - 107, election_period, size=10, color=(0.32, 0.35, 0.40)))
        commands.extend(_pdf_text(margin + 270, meta_top - 88, leader_heading, font='F2', size=10))
        commands.extend(_pdf_text(margin + 270, meta_top - 107, winner_label, size=10, color=(0.32, 0.35, 0.40)))
        if is_tie and tied_candidates:
            tie_line = f"Tied between {', '.join(tied_candidates)}"
            commands.extend(_pdf_text(margin + 270, meta_top - 121, tie_line[:44], size=9, color=(0.42, 0.45, 0.50)))

        chart_y = meta_top - 300
        _build_chart(commands, rows, margin, chart_y, 250, 150)

        summary_x = margin + 264
        commands.extend(
            _pdf_rect(summary_x, chart_y, table_width - 264, 150, fill=(0.985, 0.989, 0.995), stroke=(0.86, 0.89, 0.93))
        )
        commands.extend(_pdf_text(summary_x + 14, chart_y + 124, 'Report Summary', font='F2', size=12))
        summary_lines = [
            f"{'Result' if is_tie else 'Winner'}: {winner_label}",
            f'Turnout: {turnout:.1f}% of {registered_voters} voters',
            f'Records exported: {len(table_rows)} candidate rows',
            f'Signed digest: {signature}',
        ]
        for line_index, line in enumerate(summary_lines):
            commands.extend(
                _pdf_text(
                    summary_x + 14,
                    chart_y + 98 - (line_index * 24),
                    line,
                    size=10,
                    color=(0.28, 0.31, 0.36),
                )
            )

        table_top = chart_y - 22
        col_name_width = 185
        col_party_width = 120
        col_votes_width = 70
        col_pct_width = table_width - col_name_width - col_party_width - col_votes_width

        commands.extend(
            _pdf_rect(
                margin,
                table_top - table_header_height,
                table_width,
                table_header_height,
                fill=(0.16, 0.19, 0.26),
            )
        )
        commands.extend(_pdf_text(margin + 12, table_top - 19, 'Candidate', font='F2', size=11, color=(1, 1, 1)))
        commands.extend(_pdf_text(margin + col_name_width + 12, table_top - 19, 'Party', font='F2', size=11, color=(1, 1, 1)))
        commands.extend(_pdf_text(margin + col_name_width + col_party_width + 12, table_top - 19, 'Votes', font='F2', size=11, color=(1, 1, 1)))
        commands.extend(_pdf_text(margin + col_name_width + col_party_width + col_votes_width + 12, table_top - 19, 'Share', font='F2', size=11, color=(1, 1, 1)))

        start = page_index * rows_per_page
        end = start + rows_per_page
        page_rows = table_rows[start:end]
        row_top = table_top - table_header_height

        for row_number, row in enumerate(page_rows):
            row_y = row_top - ((row_number + 1) * row_height)
            fill = (0.985, 0.988, 0.992) if row_number % 2 == 0 else (1, 1, 1)
            commands.extend(_pdf_rect(margin, row_y, table_width, row_height, fill=fill, stroke=(0.88, 0.90, 0.93)))

            name_lines = _wrap_pdf_text(row['name'], 22)[:2]
            party_lines = _wrap_pdf_text(row['party'], 15)[:2]
            line_y = row_y + 21
            for line_index, line in enumerate(name_lines):
                commands.extend(
                    _pdf_text(
                        margin + 12,
                        line_y - (line_index * 11),
                        line,
                        font='F2' if line_index == 0 else 'F1',
                        size=10 if line_index == 0 else 9,
                    )
                )
            for line_index, line in enumerate(party_lines):
                commands.extend(
                    _pdf_text(
                        margin + col_name_width + 12,
                        line_y - (line_index * 11),
                        line,
                        size=9,
                        color=(0.32, 0.35, 0.40),
                    )
                )
            commands.extend(
                _pdf_text(
                    margin + col_name_width + col_party_width + 12,
                    row_y + 13,
                    str(row['votes']),
                    font='F2',
                    size=10,
                    color=(0.11, 0.21, 0.17),
                )
            )
            commands.extend(
                _pdf_text(
                    margin + col_name_width + col_party_width + col_votes_width + 12,
                    row_y + 13,
                    f"{row.get('percentage', 0):.1f}%",
                    font='F2',
                    size=10,
                    color=(0.15, 0.18, 0.30),
                )
            )

        commands.extend(
            _pdf_text(
                margin,
                margin,
                f'Export signature {signature} | Confidential election report',
                size=9,
                color=(0.45, 0.47, 0.51),
            )
        )
        commands.extend(
            _pdf_text(
                page_width - margin - 78,
                margin,
                f'Page {page_index + 1}/{total_pages}',
                size=9,
                color=(0.45, 0.47, 0.51),
            )
        )

        pages.append('\n'.join(commands).encode('latin-1', errors='replace'))

    objects = []
    objects.append(b'1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n')

    page_object_ids = []
    next_object_id = 3
    for _ in pages:
        page_object_ids.append(next_object_id)
        next_object_id += 2

    kids = ' '.join(f'{object_id} 0 R' for object_id in page_object_ids)
    objects.append(
        f'2 0 obj << /Type /Pages /Kids [{kids}] /Count {len(page_object_ids)} >> endobj\n'.encode('latin-1')
    )

    font_regular_id = next_object_id
    font_bold_id = next_object_id + 1

    for index, stream in enumerate(pages):
        page_object_id = page_object_ids[index]
        content_object_id = page_object_id + 1
        objects.append(
            (
                f'{page_object_id} 0 obj << /Type /Page /Parent 2 0 R '
                f'/MediaBox [0 0 {page_width} {page_height}] '
                f'/Resources << /Font << /F1 {font_regular_id} 0 R /F2 {font_bold_id} 0 R >> >> '
                f'/Contents {content_object_id} 0 R >> endobj\n'
            ).encode('latin-1')
        )
        objects.append(
            f'{content_object_id} 0 obj << /Length {len(stream)} >> stream\n'.encode('latin-1') +
            stream +
            b'\nendstream endobj\n'
        )

    objects.append(
        f'{font_regular_id} 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n'.encode('latin-1')
    )
    objects.append(
        f'{font_bold_id} 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >> endobj\n'.encode('latin-1')
    )

    pdf = bytearray(b'%PDF-1.4\n')
    offsets = [0]

    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj)

    xref_offset = len(pdf)
    pdf.extend(f'xref\n0 {len(offsets)}\n'.encode('latin-1'))
    pdf.extend(b'0000000000 65535 f \n')

    for offset in offsets[1:]:
        pdf.extend(f'{offset:010d} 00000 n \n'.encode('latin-1'))

    pdf.extend(
        (
            f'trailer << /Size {len(offsets)} /Root 1 0 R >>\n'
            f'startxref\n{xref_offset}\n%%EOF'
        ).encode('latin-1')
    )
    return bytes(pdf)


def export_results_pdf(modeladmin, request, queryset):
    report = _collect_results()
    report['report_summary'] = _build_report_summary(
        rows=report['rows'],
        total_votes=report['total_votes'],
        winner=report['winner'],
        generated_at=report['generated_at'],
        election=report['election'],
        generated_by=_request_username(request),
        is_tie=report['is_tie'],
        tied_candidates=report['tied_candidates'],
    )
    response = HttpResponse(_build_results_pdf(report), content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="election_results_report.pdf"'
    return response


export_results_pdf.short_description = 'Export Results as PDF'


def export_results_csv(modeladmin, request, queryset):
    report = _collect_results()
    generated_by = _request_username(request)
    report['report_summary'] = _build_report_summary(
        rows=report['rows'],
        total_votes=report['total_votes'],
        winner=report['winner'],
        generated_at=report['generated_at'],
        election=report['election'],
        generated_by=generated_by,
        is_tie=report['is_tie'],
        tied_candidates=report['tied_candidates'],
    )
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="election_results_report.csv"'
    writer = csv.writer(response)

    election = report['election']
    winner = report['winner']
    is_tie = report['is_tie']
    tied_candidates = report['tied_candidates']
    winner_label = 'Tie' if is_tie and tied_candidates else (winner['name'] if winner else 'No result yet')

    writer.writerow(['Election Results Report'])
    writer.writerow(['Election', election.name if election else 'All Elections'])
    writer.writerow(['Status', 'Active' if election and election.is_active else 'Closed'])
    writer.writerow(['Generated At', report['generated_at'].strftime('%d %b %Y, %I:%M %p')])
    writer.writerow(['Generated By', generated_by])
    writer.writerow(['Registered Voters', report['registered_voters']])
    writer.writerow(['Votes Cast', report['total_votes']])
    writer.writerow(['Turnout Percentage', f"{report['turnout']:.2f}%"])
    writer.writerow(['Winner', winner_label])
    writer.writerow(['Signed Summary', report['report_summary']['digest']])
    writer.writerow([])
    writer.writerow(['Candidate', 'Party', 'Votes', 'Vote Share'])

    if report['rows']:
        for row in report['rows']:
            writer.writerow([
                row['name'],
                row['party'],
                row['votes'],
                f"{row['percentage']:.2f}%",
            ])
    else:
        writer.writerow(['No votes recorded', '-', 0, '0.00%'])

    return response


export_results_csv.short_description = 'Export Results as CSV'


class VoteAdmin(admin.ModelAdmin):
    list_display = ('voter', 'encrypted_candidate')
    actions = [export_results_pdf, export_results_csv]

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context=extra_context)
        if not hasattr(response, 'context_data'):
            return response

        try:
            report = _collect_results()
            rows = report['rows']
            total_votes = report['total_votes']
            winner = report['winner']
            is_tie = report['is_tie']
            tied_candidates = report['tied_candidates']
            winner_name = winner['name'] if winner else None
            winner_votes = winner['votes'] if winner else 0

            results_html = ''

            if is_tie and tied_candidates:
                results_html += f"""
                <div style="background:#3f3520;color:#f8e7b2;padding:15px;border:1px solid #8b6d1f;border-radius:8px;margin-bottom:15px;">
                    <h2 style="margin:0;color:#f8e7b2;">Tie between {', '.join(tied_candidates)}</h2>
                </div>
                """
            elif winner_name:
                results_html += f"""
                <div style="background:#1e3a2f;color:#b7f7d0;padding:15px;border:1px solid #2f6f54;border-radius:8px;margin-bottom:15px;">
                    <h2 style="margin:0;color:#b7f7d0;">Winner: {winner_name} ({winner_votes} votes)</h2>
                </div>
                """

            results_html += (
                '<h3 style="margin:0 0 8px 0;color:var(--body-fg);">Decrypted Results</h3>'
                f'<p style="margin:0 0 12px 0;color:var(--body-quiet-color, #6b7280);">'
                f"Total votes: {total_votes} | Registered voters: {report['registered_voters']} | "
                f"Turnout: {report['turnout']:.1f}%</p>"
                '<ul style="margin:0;padding-left:22px;color:var(--body-fg);">'
            )

            for row in rows:
                results_html += (
                    f"<li>{row['name']} ({row['party']}) - {row['votes']} votes "
                    f"({row['percentage']:.1f}%)</li>"
                )

            if not rows:
                results_html += '<li>No votes available.</li>'

            results_html += '</ul>'

            response.context_data = response.context_data or {}
            response.context_data['decrypted_results'] = format_html(results_html)
        except Exception:
            response.context_data = getattr(response, 'context_data', {}) or {}
            response.context_data['decrypted_results'] = format_html(
                '<p style="color:var(--body-fg);">Unable to render decrypted results.</p>'
            )

        return response


admin.site.register(Vote, VoteAdmin)
