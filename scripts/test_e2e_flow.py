"""End-to-end integration and smoke verification test for Semantic Resume Ranker.

Walks through the complete user journey:
1. POST /api/jd: Upload Job Description text
2. POST /api/resumes: Upload all 16 sample resumes (+ 1 empty edge-case)
3. POST /api/match: Execute deterministic 5-factor matching
4. GET /api/results: Verify ranking order, top candidates, and experience caps
5. GET /api/candidates/{id}: In-depth candidate verification for:
   - Alex Chen (projects consistency, fallback scoring, headline)
   - Kevin Brooks (keyword stuffer, listed vs demonstrated count)
   - Samira Khan (experience cap applied = True, status = LOW)
   - Chloe Bennett (experience cap applied = False, status = LOW)
6. GET /api/results/export.csv: Verify 17 CSV lines, parsed columns, and cap column
"""

import csv
import io
from pathlib import Path

import httpx

BASE_URL = "http://127.0.0.1:8000/api"
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run_e2e_flow():
    print("=" * 80)
    print("STARTING LIVE END-TO-END FLOW VERIFICATION")
    print("=" * 80)

    client = httpx.Client(base_url=BASE_URL, timeout=90.0)

    # 0. Health Check
    health_res = client.get("/health")
    assert health_res.status_code == 200, f"Health check failed: {health_res.text}"
    health_data = health_res.json()
    print(f"[OK] Health check passed: {health_data['app_name']} v{health_data['version']}")
    assert health_data["models_loaded"] is True, "Models should be loaded in lifespan"

    # Reset any previous state
    del_res = client.delete("/reset")
    assert del_res.status_code == 200, f"Reset failed: {del_res.text}"
    print("[OK] Cleared test database")

    # 1. POST /api/jd
    jd_file = PROJECT_ROOT / "sample_data" / "job_description.txt"
    jd_text = jd_file.read_text(encoding="utf-8")
    jd_res = client.post("/jd", json={"text": jd_text})
    assert jd_res.status_code == 201, f"POST /api/jd failed: {jd_res.text}"
    jd_data = jd_res.json()
    jd_id = jd_data["id"]
    print(f"[OK] Step 1: Created JD #{jd_id} - '{jd_data['title']}' ({len(jd_data['required_skills'])} required skills, {len(jd_data['preferred_skills'])} preferred skills)")
    assert len(jd_data["required_skills"]) >= 8, "Should extract at least 8 required skills"
    assert jd_data["min_experience_years"] == 3.0, f"Expected 3.0 min experience years, got {jd_data['min_experience_years']}"

    # 2. POST /api/resumes
    resumes_dir = PROJECT_ROOT / "sample_data" / "resumes"
    resume_files = sorted([p for p in resumes_dir.iterdir() if p.suffix.lower() in {".pdf", ".docx"}])
    assert len(resume_files) >= 16, f"Expected at least 16 resume files, found {len(resume_files)}"

    upload_payload = []
    for p in resume_files:
        mime = (
            "application/pdf"
            if p.suffix.lower() == ".pdf"
            else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        upload_payload.append(("files", (p.name, p.read_bytes(), mime)))

    print(f"Uploading {len(upload_payload)} resumes...")
    upload_res = client.post("/resumes", files=upload_payload)
    assert upload_res.status_code == 201, f"POST /api/resumes failed: {upload_res.text}"
    batch_res = upload_res.json()
    print(f"[OK] Step 2: Uploaded {batch_res['total_uploaded']} resumes: {batch_res['successful']} successful, {batch_res['failed']} failed")
    assert batch_res["successful"] == 16, f"Expected 16 successful parses, got {batch_res['successful']}"
    assert batch_res["failed"] == 1, f"Expected 1 failed empty edge-case, got {batch_res['failed']}"

    # 3. POST /api/match
    print("Computing deterministic 5-factor match...")
    match_res = client.post("/match", json={"jd_id": jd_id})
    assert match_res.status_code == 200, f"POST /api/match failed: {match_res.text}"
    match_data = match_res.json()
    print(f"[OK] Step 3: Match completed for {match_data['total_candidates']} candidates")
    assert match_data["total_candidates"] == 16, f"Expected 16 matched candidates, got {match_data['total_candidates']}"

    # 4. GET /api/results?jd_id={id}
    results_res = client.get(f"/results?jd_id={jd_id}")
    assert results_res.status_code == 200, f"GET /api/results failed: {results_res.text}"
    ranked_list = results_res.json()["results"]
    assert len(ranked_list) == 16, f"Expected 16 results, got {len(ranked_list)}"

    print("\n--- RANKED CANDIDATES ---")
    candidate_by_name = {}
    for rank, item in enumerate(ranked_list, start=1):
        candidate_by_name[item["name"]] = item
        cap_str = " [CAP APPLIED]" if item["experience_cap_applied"] else ""
        print(f"#{rank:<2} {item['name']:<22} | Score: {item['final_score']:5.1f}% | Exp: {item['experience_years']:4.1f}y | Status: {item['status_label']:<6}{cap_str}")

    # Verify ranking order matches Phase 2 specifications:
    # Top genuine candidates: Alex Chen, Sarah Lindqvist, David Kim, Jordan Taylor, Rachel Green in top tier
    top_5_names = [ranked_list[i]["name"] for i in range(5)]
    print(f"\nTop 5 Candidates: {top_5_names}")
    assert any("Jordan" in n for n in top_5_names), "Jordan Taylor should be in top tier"
    assert any("David" in n for n in top_5_names), "David Kim should be in top tier"
    assert any("Alex" in n for n in top_5_names), "Alex Chen should be in top tier"
    assert any("Sarah" in n for n in top_5_names), "Sarah Lindqvist should be in top tier"

    # Kevin Brooks (keyword stuffer) ranks below Jordan, David, and Rachel
    assert "Kevin Brooks" in candidate_by_name, "Kevin Brooks must be in results"
    assert "Jordan Taylor" in candidate_by_name
    assert "David Kim" in candidate_by_name
    assert "Rachel Green" in candidate_by_name

    kevin_score = candidate_by_name["Kevin Brooks"]["final_score"]
    jordan_score = candidate_by_name["Jordan Taylor"]["final_score"]
    david_score = candidate_by_name["David Kim"]["final_score"]
    rachel_score = candidate_by_name["Rachel Green"]["final_score"]

    print(f"\nScores Check: Jordan={jordan_score:.1f}, David={david_score:.1f}, Rachel={rachel_score:.1f} vs Kevin={kevin_score:.1f}")
    assert kevin_score < jordan_score, f"Kevin Brooks ({kevin_score}) should score lower than Jordan Taylor ({jordan_score})"
    assert kevin_score < david_score, f"Kevin Brooks ({kevin_score}) should score lower than David Kim ({david_score})"
    assert kevin_score < rachel_score, f"Kevin Brooks ({kevin_score}) should score lower than Rachel Green ({rachel_score})"
    print("[OK] Step 4: Ranking order verified (keyword stuffer penalized below genuine matches)")

    # 5. GET /api/candidates/{id}?jd_id={id} checks
    print("\n--- STEP 5: DETAILED CANDIDATE IN-DEPTH INSPECTION ---")

    # 5a. Alex Chen
    alex_id = candidate_by_name["Alex Chen"]["candidate_id"]
    alex_res = client.get(f"/candidates/{alex_id}?jd_id={jd_id}")
    assert alex_res.status_code == 200
    alex_data = alex_res.json()
    print(f"\n[Alex Chen] Sections: {alex_data['extracted_info']['sections_found']}")
    print(f"[Alex Chen] Project Score: {alex_data['sub_scores']['project']:.1f}%")
    print(f"[Alex Chen] Headline: {alex_data['headline']}")
    assert "projects" not in alex_data["extracted_info"]["sections_found"], "Alex Chen has no dedicated projects section"
    assert alex_data["sub_scores"]["project"] > 0, "Alex Chen should have project fallback score from experience sentences"
    assert alex_data["headline"], "Alex Chen should have a clear headline"

    # 5b. Kevin Brooks
    kevin_id = candidate_by_name["Kevin Brooks"]["candidate_id"]
    kevin_res = client.get(f"/candidates/{kevin_id}?jd_id={jd_id}")
    assert kevin_res.status_code == 200
    kevin_data = kevin_res.json()
    dem_count = sum(1 for s in kevin_data["matched_skills"] if s.get("evidence_source") == "demonstrated")
    list_count = sum(1 for s in kevin_data["matched_skills"] if s.get("evidence_source") == "listed")
    print(f"[Kevin Brooks] Demonstrated skills: {dem_count}, Listed-only skills: {list_count}")
    assert list_count > dem_count, f"Kevin Brooks should have mostly listed-only skills (listed={list_count}, dem={dem_count})"

    # 5c. Samira Khan
    samira_id = candidate_by_name["Samira Khan"]["candidate_id"]
    samira_res = client.get(f"/candidates/{samira_id}?jd_id={jd_id}")
    assert samira_res.status_code == 200
    samira_data = samira_res.json()
    print(f"[Samira Khan] Experience: {samira_data['found_years']:.1f}y, Cap Applied: {samira_data['experience_cap_applied']}, Status: {samira_data['status_label']}")
    assert samira_data["experience_cap_applied"] is True, "Samira Khan must have experience_cap_applied == True"
    assert samira_data["status_label"] == "LOW", f"Samira Khan status must be LOW, got {samira_data['status_label']}"

    # 5d. Chloe Bennett
    chloe_id = candidate_by_name["Chloe Bennett"]["candidate_id"]
    chloe_res = client.get(f"/candidates/{chloe_id}?jd_id={jd_id}")
    assert chloe_res.status_code == 200
    chloe_data = chloe_res.json()
    print(f"[Chloe Bennett] Score: {chloe_data['overall_score']:.1f}%, Cap Applied: {chloe_data['experience_cap_applied']}, Status: {chloe_data['status_label']}")
    assert chloe_data["experience_cap_applied"] is False, "Chloe Bennett was already LOW by score, experience_cap_applied must be False"
    assert chloe_data["status_label"] == "LOW", f"Chloe Bennett status must be LOW, got {chloe_data['status_label']}"
    print("[OK] Step 5: All 4 detailed candidate checks verified successfully")

    # 6. GET /api/results/export.csv?jd_id={id}
    csv_res = client.get(f"/results/export.csv?jd_id={jd_id}")
    assert csv_res.status_code == 200, f"CSV export failed: {csv_res.text}"
    assert "text/csv" in csv_res.headers.get("content-type", "")

    csv_text = csv_res.text
    csv_reader = list(csv.reader(io.StringIO(csv_text)))
    print(f"\n[OK] Step 6: CSV Export retrieved. Total CSV rows: {len(csv_reader)}")
    assert len(csv_reader) == 17, f"Expected 17 rows (1 header + 16 candidates), got {len(csv_reader)}"

    header = csv_reader[0]
    print(f"CSV Header columns: {header}")
    assert "Rank" in header
    assert "Candidate Name" in header
    assert any("Final Score" in col for col in header)
    assert any("Status" in col for col in header)
    assert any("Experience Cap" in col for col in header)

    # Verify rows can be parsed
    samira_row = next(r for r in csv_reader[1:] if "Samira Khan" in r[1])
    cap_col_idx = header.index("Experience Cap Applied")
    assert samira_row[cap_col_idx].lower() == "true", f"Expected Samira Khan cap column to be True, got {samira_row[cap_col_idx]}"

    print("\n" + "=" * 80)
    print("ALL END-TO-END VERIFICATION CHECKS PASSED PERFECTLY!")
    print("=" * 80)


if __name__ == "__main__":
    run_e2e_flow()
