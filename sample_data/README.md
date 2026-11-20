# Sample Dataset (Synthetic)

All resumes and job descriptions contained in this directory and its subdirectories are **100% synthetic and hand-authored**.

## Notice
- **No Real Personal Data**: Every candidate name, email address (using the reserved RFC 2606 `@example.com` domain), phone number (`+1-555-xxxx`), employer name, and project description is synthetic and hand-authored.
- **Purpose**: These benchmark files serve as standardized evaluation fixtures to test deterministic parsing, keyword-stuffer defenses, two-column PDF coordinate extraction, interval date merging, edge-case failure modes (empty/scanned PDFs), and semantic scoring calibration.

---

## Test Sets & Benchmark Roles

### 1. Python / FastAPI Benchmark Set
- **Job Description**: `sample_data/job_description.txt` (Senior Backend Python Engineer)
- **Resumes Directory**: `sample_data/resumes/`
- **Personas Evaluated**:
  1. `01_strong_match_alex_chen.pdf`: High-tenure Python/FastAPI engineer (strong technical match).
  2. `02_good_match_jordan_taylor.docx`: Mid-level backend developer with Python, PostgreSQL, and Docker.
  3. `03_partial_match_priya_sharma.pdf`: Django & Flask engineer testing curated related-skills credit.
  4. `04_wrong_domain_liam_oconnor.docx`: iOS/Swift frontend engineer (negative control, wrong domain).
  5. `05_career_changer_maya_lin.pdf`: Transitioning from QA/testing to backend development.
  6. `06_keyword_stuffer_kevin_brooks.docx`: Stuffs 13 JD keywords only in a skills list with 0 in work history.
  7. `07_same_skills_diff_wording_elena.pdf`: Equivalent technical capabilities described using non-keyword synonyms.
  8. `08_overqualified_marcus_vance.pdf`: Staff/Principal engineer with 16.9 years of experience.
  9. `09_fresher_with_projects_samira.docx`: High project scores but 0.0y work experience (tests experience cap).
  10. `10_two_column_david_kim.pdf`: Two-column layout testing visual coordinate sorting and education date isolation.
  11. `11_good_match_rachel_green.pdf`: Strong mid-level backend engineer with clear work experience.
  12. `12_data_engineer_carlos_mendes.docx`: Data engineering specialist with partial overlap.
  13. `13_scanned_empty_edge_case.pdf`: Empty/scanned raster PDF testing graceful non-crashing error handling.
  14. `14_minimal_candidate_chloe.docx`: Junior candidate with sparse text and low skill coverage.
  15. `15_mid_level_nodejs_dev.docx`: Node.js/TypeScript backend engineer (unseen test fixture).
  16. `16_strong_fastapi_alt_wording.pdf`: Strong FastAPI engineer with alternative phrasing (unseen test fixture).
  17. `17_devops_cloud_engineer.pdf`: Cloud infrastructure engineer (unseen test fixture).

---

### 2. Java / Spring Boot Set
- **Job Description**: `sample_data/java_test/sample_JD_java_spring_boot.txt` (Senior Java / Spring Boot Engineer)
- **Resumes Directory**: `sample_data/java_test/`
- **Personas Evaluated**:
  1. `01_aarav_mehta_strong_match.pdf`: Strong match with extensive Spring Boot, Microservices, and Hibernate experience.
  2. `02_neha_kapoor_good_match.docx`: Solid backend developer with Java, Spring Boot, and PostgreSQL.
  3. `03_rohan_das_legacy_java.pdf`: Legacy Java developer (Java EE, Struts, EJB) testing partial stack alignment.
  4. `04_simran_kaur_different_wording.docx`: Equivalent technical skills using alternative wording and synonyms.
  5. `05_vikram_nair_keyword_stuffer.pdf`: Candidate listing numerous unverified Java keywords.
  6. `06_ananya_iyer_fresher_with_projects.docx`: High project scores but minimal tenure (testing experience caps).
  7. `07_karan_malhotra_wrong_domain.pdf`: Embedded C/C++ firmware engineer (negative control, wrong domain).

---

### 3. Data Scientist Set
- **Job Description**: `sample_data/data_scientist_test/sample_JD_data_scientist.txt` (Senior Data Scientist)
- **Resumes Directory**: `sample_data/data_scientist_test/`
- **Personas Evaluated**:
  1. `01_priyanka_reddy_strong_match.pdf`: High-tenure ML/Data Scientist with scikit-learn, PyTorch, and NLP experience.
  2. `02_arjun_bhatt_good_match.docx`: Data Scientist with Python, SQL, statistical modeling, and ML pipelines.
  3. `03_meera_joshi_two_column.pdf`: Two-column layout testing visual coordinate sorting on data science profiles.
  4. `04_siddharth_rao_analyst_pivot.docx`: Data analyst transitioning into data science (partial skills overlap).
  5. `05_tanvi_shah_keyword_stuffer.pdf`: Keyword stuffer with list-only ML and AI buzzwords.
  6. `06_rahul_verma_overlapping_dates.docx`: Multiple concurrent contracts testing non-overlapping date deduplication.
  7. `07_divya_menon_fresher.pdf`: Academic graduate with thesis projects but no commercial work experience.

---

### 4. Digital Marketing Set
- **Job Description**: `sample_data/marketing_test/sample_JD_digital_marketing_manager.txt` (Digital Marketing Manager)
- **Resumes Directory**: `sample_data/marketing_test/`
- **Personas Evaluated**:
  1. `01_ishaan_malhotra_strong_match.pdf`: Experienced marketing manager with SEO, SEM, Google Analytics, and growth campaigns.
  2. `02_pooja_nambiar_good_match.docx`: Performance marketer with Meta Ads, HubSpot, and email marketing.
  3. `03_nikhil_chawla_different_wording.docx`: Marketing skills described using alternative phrasing and campaign metrics.
  4. `04_farah_siddiqui_pr_communications.pdf`: PR and corporate communications specialist pivoting to growth marketing.
  5. `05_gaurav_tiwari_keyword_stuffer.pdf`: Keyword stuffer with excessive listed marketing terminology.
  6. `06_sneha_pillai_fresher.docx`: Marketing graduate with social media internship and university campaigns.
  7. `07_rajesh_kulkarni_wrong_domain.pdf`: Hardware network engineer (negative control, completely wrong domain).
