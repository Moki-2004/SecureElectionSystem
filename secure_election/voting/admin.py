from django.contrib import admin
from .models import Vote
from elections.models import Candidate
from secure_election.utils.encryption import decrypt_vote
from collections import Counter
from django.utils.html import format_html

# PDF imports
from django.http import HttpResponse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


# ============================
# 📄 PDF EXPORT FUNCTION
# ============================
def export_results_pdf(modeladmin, request, queryset):
    votes = Vote.objects.all()
    decrypted_ids = []

    for vote in votes:
        try:
            cid = decrypt_vote(vote.encrypted_candidate)
            decrypted_ids.append(int(cid))
        except:
            continue

    counts = Counter(decrypted_ids)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="election_results.pdf"'

    p = canvas.Canvas(response, pagesize=letter)
    y = 750

    p.setFont("Helvetica-Bold", 16)
    p.drawString(200, y, "Election Results")
    y -= 40

    p.setFont("Helvetica", 12)

    for cid, total in counts.items():
        try:
            candidate = Candidate.objects.get(id=cid)
            line = f"{candidate.name} : {total} votes"
            p.drawString(100, y, line)
            y -= 25
        except:
            pass

    p.save()
    return response

export_results_pdf.short_description = "📄 Export Results as PDF"


# ============================
# 🗳 ADMIN CLASS
# ============================
class VoteAdmin(admin.ModelAdmin):
    list_display = ("voter", "encrypted_candidate")
    actions = [export_results_pdf]

    # 🔐 Decrypted Results Section
    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context=extra_context)

        try:
            votes = Vote.objects.all()
            decrypted_ids = []

            # 🔓 Decrypt votes
            for vote in votes:
                try:
                    cid = decrypt_vote(vote.encrypted_candidate)
                    decrypted_ids.append(int(cid))
                except:
                    continue

            counts = Counter(decrypted_ids)

            # ==========================
            # 🏆 WINNER LOGIC
            # ==========================
            winner_name = None
            winner_votes = 0

            if counts:
                top_id = max(counts, key=counts.get)
                winner_votes = counts[top_id]
                winner_name = Candidate.objects.get(id=top_id).name

            # ==========================
            # Build HTML output
            # ==========================
            results_html = ""

            # Winner banner
            if winner_name:
                results_html += f"""
                <div style="background:#e6ffed;padding:15px;border-radius:8px;margin-bottom:15px">
                    <h2>🏆 Winner: {winner_name} ({winner_votes} votes)</h2>
                </div>
                """

            # All results
            results_html += "<h3>🔓 Decrypted Results</h3><ul>"

            for cid, total in counts.items():
                try:
                    candidate = Candidate.objects.get(id=cid)
                    results_html += f"<li>{candidate.name} — {total} votes</li>"
                except:
                    pass

            results_html += "</ul>"

            response.context_data["decrypted_results"] = format_html(results_html)

        except Exception as e:
            print("Result error:", e)

        return response


# Register admin
admin.site.register(Vote, VoteAdmin)