# Algorithmic Specification & Mathematical Rationale

This document provides a formal, comprehensive explanation of the scoring pipeline, mathematical formulations, calibration bounds, keyword-stuffer defenses, edge-case policies, worked numeric examples, and engineering trade-offs implemented in the **AI-Based Resume Matching & Ranking Engine**.

---

## 1. Overall Architecture & Scoring Formula

The system computes an overall candidate match score on a calibrated scale of $[0.0, 100.0]$ using a linear combination of five orthogonal factors:

$$\text{FinalScore} = 0.40 \cdot S_{\text{skills}} + 0.25 \cdot S_{\text{semantic}} + 0.20 \cdot S_{\text{experience}} + 0.10 \cdot S_{\text{education}} + 0.05 \cdot S_{\text{project}}$$

All factor weights are defined centrally in `backend/app/config.py` and sum strictly to $1.0$:
- **Skills Score ($S_{\text{skills}}$)**: $40\%$ (`weight_skills = 0.40`)
- **Semantic Fit Score ($S_{\text{semantic}}$)**: $25\%$ (`weight_semantic = 0.25`)
- **Experience Score ($S_{\text{experience}}$)**: $20\%$ (`weight_experience = 0.20`)
- **Education Score ($S_{\text{education}}$)**: $10\%$ (`weight_education = 0.10`)
- **Project Score ($S_{\text{project}}$)**: $5\%$ (`weight_project = 0.05`)

---

## 2. Granular Component Formulations

### 2.1 Skill Score ($S_{\text{skills}}$), Open-Vocabulary Extraction & Keyword-Stuffer Defense

Skill matching combines open-vocabulary discovery, canonical taxonomy aliasing, domain-curated relationship graphs, and a high-threshold embedding fallback.

#### (a) Job Description Priority Weights & Deduplication
- **Required Skills**: $w = 2.0$ (`required_skill_weight = 2.0`)
- **Preferred Skills**: $w = 1.0$ (`preferred_skill_weight = 1.0`)
- **Strict Deduplication**: When parsing JDs, any skill that appears in both "Required Skills" and "Preferred Skills" is deduplicated and retained exclusively in `required_skills`. Skills appearing only in general responsibilities or overview text are never elevated to required.

#### (b) Open-Vocabulary Extraction
To prevent taxonomy blindspots across diverse engineering, data science, and domain stacks:
- Every bullet or comma-separated item under explicit "Required Skills" / "Preferred Skills" (JD) or under "SKILLS / TECHNOLOGIES" (resume) is extracted as a skill, even if not yet in the pre-built taxonomy.
- The taxonomy is used for canonical normalization and alias mapping. Unknown/emerging skills are matched via normalized string equality and the $\ge 0.75$ embedding fallback.

#### (c) Evidence Source Tracking (Keyword-Stuffer Defense)
To prevent candidates from gaming the system by listing dozens of keywords without real experience, each candidate skill is classified by its source of evidence:
- **`demonstrated`** (Multiplier = $1.00$): The skill (or its canonical alias) appears in the candidate's actual work experience bullet points or project deliverables.
- **`listed`** (Multiplier = $0.50$, configured via `listed_only_credit = 0.50`): The skill appears only in a top-level "Skills" or "Technologies" list without documented usage in work history.

#### (d) Multi-Tier Credit Evaluation
For each JD skill, credit is calculated as follows:
1. **Tier 1: Exact Match or Canonical Alias**:
   Matches canonical names or known aliases in `skills_taxonomy.json` (e.g., `Postgres` $\to$ `PostgreSQL`, `k8s` $\to$ `Kubernetes`, `sklearn` $\to$ `scikit-learn`).
   $$\text{Credit} = 1.0 \times \text{Multiplier}$$
2. **Tier 2A: Curated Taxonomy Relations (`RELATED_SKILLS`)**:
   Explicit domain relations with curated credit values prevent spurious embedding matches:
   - `FastAPI` $\longleftrightarrow$ `Flask` ($0.65$), `Django` ($0.60$)
   - `Spring Boot` $\longleftrightarrow$ `Spring Framework` ($0.60$), `Hibernate` $\longleftrightarrow$ `JPA` ($0.80$)
   - `scikit-learn` $\longleftrightarrow$ `Machine Learning` ($0.70$), `PyTorch` $\longleftrightarrow$ `TensorFlow` ($0.70$), `Tableau` $\longleftrightarrow$ `Power BI` ($0.80$)
   - `PostgreSQL` $\longleftrightarrow$ `MySQL` ($0.70$), `SQLite` ($0.60$), `SQL` ($0.75$)
   - `Docker` $\longleftrightarrow$ `Podman` ($0.80$), `Kubernetes` ($0.60$)
   - `REST APIs` $\longleftrightarrow$ `GraphQL` ($0.60$)
   - `AWS` $\longleftrightarrow$ `GCP` ($0.70$), `Azure` ($0.70$)
   - *(Unrelated pairs such as `Redis` $\leftrightarrow$ `PostgreSQL` are explicitly excluded).*
   $$\text{Credit} = \text{CuratedCredit} \times \text{Multiplier}$$
3. **Tier 2B: Embedding Fallback (Strict Threshold)**:
   If no exact or curated relation matches, cosine similarity between skill embeddings is computed. To prevent loose false positives, credit is awarded **only if** $\text{cosine} \ge 0.75$ (`skill_embed_threshold = 0.75`). Any match below $0.75$ receives $0.0$ credit.
   $$\text{Credit} = \text{cosine} \times \text{Multiplier} \quad (\text{if } \text{cosine} \ge 0.75, \text{ else } 0.0)$$
4. **Missing Skill**:
   $$\text{Credit} = 0.0$$

The final skill score is the weighted average across all JD skills:
$$S_{\text{skills}} = \left( \frac{\sum_{i \in \text{JD Skills}} \text{Credit}_i \cdot w_i}{\sum_{i \in \text{JD Skills}} w_i} \right) \times 100$$

---

### 2.2 Semantic Fit Score ($S_{\text{semantic}}$) & Calibration

Semantic similarity measures holistic alignment between the candidate's actual work experience and the responsibilities/requirements described in the Job Description.

1. **Sentence Chunking & Embedding**:
   The JD text and the resume's experience section are split into individual sentences using spaCy (`en_core_web_sm`). Each sentence is converted into a 384-dimensional dense vector using `all-MiniLM-L6-v2`.
2. **Top-$k$ Cross-Similarity**:
   For each JD requirement sentence, cosine similarity is computed across all resume experience sentences. The top $k=5$ (`semantic_top_k = 5`) highest-scoring sentence pairs are extracted, and their arithmetic mean $\bar{c}$ is calculated.
3. **Distribution-Aware Linear Calibration**:
   Raw cosine similarities for English technical text using `all-MiniLM-L6-v2` naturally cluster between $0.30$ and $0.75$. Uncalibrated cosines cause strong candidates to clump at 100% or weak candidates to score artificially high.
   Based on the empirical distribution of the benchmark dataset, the calibration bounds are configured in `backend/app/config.py`:
   - $c_{\min} = 0.28$ (`semantic_min_cosine = 0.28`)
   - $c_{\max} = 0.78$ (`semantic_max_cosine = 0.78`)
   $$S_{\text{semantic}} = \text{clamp}\left( \frac{\bar{c} - c_{\min}}{c_{\max} - c_{\min}} \cdot 100, \, 0.0, \, 100.0 \right)$$
   This calibration maps a strong match (raw cosine $\approx 0.74$) to $\approx 92\%$, rather than an unrealistic 100%.

---

### 2.3 Experience Score ($S_{\text{experience}}$), Relevant vs Total Tenure, & Hybrid Role Relevance

Experience scoring evaluates relevant professional maturity rather than generic tenure, preventing unrelated careers (e.g., content writing, customer service) from inflating technical qualifications.

#### (a) Invariant Tenure Properties
- **Total Experience ($Y_{\text{tot}}$)**: Verified calendar tenure derived strictly from chronological date intervals in work experience, completely unaffected by job title or role relevance.
- **Relevant Experience ($Y_{\text{rel}}$)**: Role-weighted tenure reflecting technical alignment with JD responsibilities.
- **Fundamental Invariant**: $Y_{\text{rel}} \le Y_{\text{tot}}$ strictly holds for every candidate across all domains.

#### (b) Explainable 3-Tier Role Relevance
For each discrete employment role (extracted with header, dates, and bullet deliverables), relevance $R_{\text{role}} \in \{0.0, 0.5, 1.0\}$ is determined deterministically by three explainable tiers:

1. **Tier 1.0 (Full Credit)**:
   - Awarded if the role demonstrates $\ge 2$ JD skills (required or preferred) in its title/bullets.
   - Validated via exact, alias, or light-stemmed match (`role_min_skills_full_credit = 2`). Curated-related skills do *not* count as direct evidence for role relevance.
2. **Tier 0.5 (Half Credit)**:
   - Awarded if the role demonstrates exactly 1 JD skill, OR demonstrates 0 skills but its bullet deliverables reach the semantic threshold against JD responsibilities (mean top-3 cosine $\bar{c}_{\text{role}} \ge 0.55$, configured via `role_semantic_threshold = 0.55`).
3. **Tier 0.0 (No Credit)**:
   - Assigned when 0 JD skills are demonstrated and bullet semantic cosine is below threshold ($\bar{c}_{\text{role}} < 0.55$).
   - Completely zeroes out non-technical roles (e.g., Customer Support, Content Writing).
#### (c) Non-Overlapping Timeline Slicing
To handle overlapping jobs or freelance consulting without double-counting:
- All active roles are sliced into disjoint timeline segments $[t_i, t_{i+1}]$.
- For each segment, the candidate receives the maximum relevance among active positions:
  $$Y_{\text{rel}} = \sum_{i} \Delta t_i \cdot \max_{r \in \text{active}(i)} R_{r}, \quad Y_{\text{rel}} = \min(Y_{\text{rel}}, Y_{\text{tot}})$$

#### (d) Experience Score Formula
If the JD specifies $Y_{\text{req}}$ required years:
$$S_{\text{experience}} = \min\left( \frac{Y_{\text{rel}}}{Y_{\text{req}}} \cdot 100, \, 100.0 \right)$$

#### (e) Known Limitation: Single Generic Skill Crediting
Under the Tier 0.5 rule, a role earns half-credit ($R_{\text{role}} = 0.5$) if it demonstrates exactly 1 JD skill in its title or bullet deliverables. When a role demonstrates only a single ubiquitous or generic skill (e.g., `REST APIs`, `Git`, `SQL`) without any core architectural or domain-specific technologies (e.g., `Spring Boot`, `Hibernate`, `PyTorch`), that position still receives 50% tenure credit despite low semantic similarity to the primary job responsibilities (for example, a Frontend Developer mentioning `REST APIs` against a Java Backend JD with cosine 0.345, or a Financial Analyst mentioning basic `Python` scripting with cosine 0.264). A prospective future enhancement is defining a curated list of horizontal generic skills that require companion domain skills to qualify for Tier 0.5 relevance credit.

---

### 2.4 Education Score ($S_{\text{education}}$) & Degree Hierarchy

Degree qualifications are extracted using robust punctuation-tolerant regex patterns and ordered according to an academic hierarchy configured in `backend/app/config.py`:

| Degree Level | Patterns & Equivalencies | Hierarchy Rank ($R$) | Normalized Score |
|:---|:---|:---:|:---:|
| **PhD / Doctorate** | `Ph.D.`, `PhD`, `Doctorate`, `Doctor of Philosophy` | 4 | $100.0\%$ |
| **Master's** | `M.Sc.`, `MSc`, `M.S.`, `MS`, `M.Tech`, `M.E.`, `MBA`, `MCA`, `M.A.`, `MFA`, `M.Ed`, `M.Pharm`, `M.Arch`, `LLM`, `PGDM`, `PGDBM`, `Master of ...`, `PG Diploma` *(Note: Indian management diplomas `PGDM` and `PGDBM` are treated as Master-equivalent)* | 3 | $90.0\%$ |
| **Bachelor's** | `B.Sc.`, `BSc`, `B.E.`, `B.Tech`, `BCA`, `B.Com`, `BCom`, `B.A.`, `BBA`, `BBM`, `BMS`, `BFA`, `B.Ed`, `B.Pharm`, `B.Arch`, `LLB`, `Bachelor of ...` | 2 | $75.0\%$ |
| **Diploma / Associate** | `Diploma`, `Associate Degree` | 1 | $50.0\%$ |
| **None detected** | No recognized degree statement | 0 | $25.0\%$ |

- **Degree Hierarchy Resolution**: When multiple degrees appear on a resume (e.g. `B.Com` + `MBA` or `B.Sc.` + `M.Sc.`), the parser automatically takes the highest degree rank.
- **JD Education Requirement Rule**: When extracting education requirements from a Job Description, degrees mentioned with preference markers (`plus`, `preferred`, `desirable`, `advantage`, `nice to have`, `a bonus`, `ideally`, `optional`) are ignored as optional preferences. Among remaining required degrees in the qualification statement, the system takes the **LOWEST** level (e.g., "Bachelor's or Master's" requires Bachelor's since either level satisfies the requirement).
- If candidate rank $R_{\text{cand}} \ge R_{\text{req}}$: $S_{\text{education}} = 100.0\%$.
- If candidate rank $R_{\text{cand}} < R_{\text{req}}$:
  $$S_{\text{education}} = \max\left( 25.0, \, 100.0 - 25.0 \cdot (R_{\text{req}} - R_{\text{cand}}) \right)$$

---

### 2.5 Project Score ($S_{\text{project}}$)

Project scoring evaluates hands-on technical deliverables:
1. **Dedicated Projects Section**:
   If a dedicated project section exists, sentences describing projects that contain at least one recognized technical skill are embedded against the JD requirements. Raw top-sentence cosine similarities are calibrated over $[0.25, 0.75]$ (`project_min_cosine = 0.25`, `project_max_cosine = 0.75`). Dedicated projects can earn up to $100.0\%$.
2. **Experience Fallback with Score Cap**:
   If no dedicated projects section exists (e.g., Alex Chen), the system extracts high-content technical achievement sentences from the work experience section. To maintain fairness with candidates who documented independent projects, fallback contribution is capped at $70.0\%$ (`fallback_project_cap = 70.0%`).

---

## 3. Thresholds & Experience Cap Policy

### 3.1 Status Classification Thresholds
Candidates are grouped into three recruiter-facing tiers based on final score:
- **`HIGH`**: $\text{FinalScore} \ge 80.0\%$ (`threshold_high = 80.0`)
- **`MEDIUM`**: $60.0\% \le \text{FinalScore} < 80.0\%$ (`threshold_medium = 60.0`)
- **`LOW`**: $\text{FinalScore} < 60.0\%$

### 3.2 Hard Experience Cap Rule
When a job description states a hard minimum experience requirement, candidates lacking core professional maturity should not be recommended as `HIGH` or `MEDIUM`, regardless of keyword alignment or project scores.

- **Rule**: If relevant experience $Y_{\text{rel}} < 0.50 \cdot Y_{\text{req}}$ (`hard_req_experience_ratio_cap = 0.50`), the status label is **capped at `LOW`**.
- **Lowering Flag**: The boolean `experience_cap_applied` is set to `True` **only if** the candidate's score would have placed them in `HIGH` or `MEDIUM` and was actively downgraded to `LOW`.
  - *Example (Samira Khan)*: Score = $61.38\%$ (would be `MEDIUM`), Relevant Experience = $0.0\text{y} < 1.5\text{y}$ $\implies$ Status = `LOW`, `experience_cap_applied = True`.
  - *Example (Divya Menon)*: Score = $40.52\%$ (already `LOW` by score), Relevant Experience = $0.1\text{y} < 1.5\text{y}$ $\implies$ Status = `LOW`, `experience_cap_applied = False` (cap did not lower label).
  - *Example (Tanvi Shah)*: Score = $25.50\%$ (already `LOW` by score), Relevant Experience = $0.0\text{y} < 1.5\text{y}$ $\implies$ Status = `LOW`, `experience_cap_applied = False`.

---

## 4. Worked Numerical Examples (From Live API Output)

### Example 1: High Match Candidate (Alex Chen)
- **Role**: Senior Backend Python Engineer
- **JD Requirement**: 3.0+ years experience, Bachelor's degree, FastAPI, PostgreSQL, Docker, Pytest.
- **Candidate Data**: 7.9 years total experience, 7.9 years relevant experience, Bachelor's degree, demonstrated FastAPI, PostgreSQL, Docker in work history. No dedicated projects section (fallback from work experience used).

#### Sub-Score Breakdown:
1. **Skill Score ($S_{\text{skills}}$) = 91.04%**:
   Matches 13 of 15 JD skills; 12 demonstrated in work history (multiplier 1.0), 1 listed only (multiplier 0.5), 1 partial (GCP $\leftrightarrow$ AWS, 70% credit), 1 missing.
2. **Semantic Score ($S_{\text{semantic}}$) = 91.81%**:
   Mean raw cosine of top-5 sentence pairs = $0.739$.
   $$S_{\text{semantic}} = \frac{0.739 - 0.28}{0.78 - 0.28} \cdot 100 = \frac{0.459}{0.50} \cdot 100 = 91.81\%$$
3. **Experience Score ($S_{\text{experience}}$) = 100.0%**:
   Both roles ("Senior Backend Developer", "Backend Software Engineer") have $1.00$ relevance.
   $$\min\left( \frac{7.9}{3.0} \cdot 100, \, 100.0 \right) = 100.0\%$$
4. **Education Score ($S_{\text{education}}$) = 100.0%**:
   Bachelor's degree satisfies requirements.
5. **Project Score ($S_{\text{project}}$) = 69.40%**:
   Derived from technical sentences in work history; capped below $70.0\%$.

#### Final Score Calculation:
$$\text{FinalScore} = (0.40 \times 91.04) + (0.25 \times 91.81) + (0.20 \times 100.0) + (0.10 \times 100.0) + (0.05 \times 69.40)$$
$$\text{FinalScore} = 36.42 + 22.95 + 20.00 + 10.00 + 3.47 = \mathbf{92.84\%}$$
- **Status**: **`HIGH`** ($\ge 80.0\%$)
- **Experience Cap Applied**: `False`

---

### Example 2: Contrast Keyword-Stuffer Candidate (Kevin Brooks)
- **Candidate Profile**: 2.9 years total experience. Listed 13 matching JD keywords (FastAPI, PostgreSQL, Docker, Redis, Kubernetes, etc.) inside a "Skills" block, but work history contains 0 technical deliverables or verified skills.

#### Sub-Score Breakdown:
1. **Skill Score ($S_{\text{skills}}$) = 43.75%**:
   All 13 skills are categorized as `listed` only. Multiplier $0.50$ is applied to every skill, cutting credit in half ($13 \times 0.50 = 6.5$ effective matches).
2. **Semantic Score ($S_{\text{semantic}}$) = 26.59%**:
   Work history sentences lack technical substance. Mean top-5 cosine = $0.413$.
   $$S_{\text{semantic}} = \frac{0.413 - 0.28}{0.78 - 0.28} \cdot 100 = \frac{0.133}{0.50} \cdot 100 = 26.59\%$$
3. **Experience Score ($S_{\text{experience}}$) = 0.0%**:
   Independent projects role had no technical skills and semantic alignment below threshold; relevant experience = $0.0$ years.
   $$\frac{0.0}{3.0} \cdot 100 = 0.0\%$$
4. **Education Score ($S_{\text{education}}$) = 100.0%**:
   Bachelor's degree matches requirement.
5. **Project Score ($S_{\text{project}}$) = 10.0%**:
   Minimal project content detected.

#### Final Score Calculation:
$$\text{FinalScore} = (0.40 \times 43.75) + (0.25 \times 26.59) + (0.20 \times 0.0) + (0.10 \times 100.0) + (0.05 \times 10.0)$$
$$\text{FinalScore} = 17.50 + 6.65 + 0.00 + 10.00 + 0.50 = \mathbf{34.65\%}$$
- **Status**: **`LOW`** ($< 60.0\%$)
- **Rank**: **#15 of 16** candidates.
- **Why it worked**: The combination of `listed_only_credit = 0.50`, chunk-level semantic similarity, and hybrid role relevance successfully penalized Kevin Brooks, dropping him far below genuine practitioners (Jordan Taylor `77.5%`, David Kim `79.5%`, Rachel Green `71.3%`).

---

## 5. Design Decisions and Trade-Offs

### 5.1 Why Deterministic Scoring Instead of Generative LLMs?
- **Auditable & Explainable**: Every line of score is traceable to an exact equation, verified date interval, or matched skill token. Evaluators and compliance teams can inspect the exact formula.
- **100% Offline & Cost-Free**: Operates on CPU without external API keys, tokens, rate limits, or network dependencies.
- **Consistency**: The same resume scored against the same JD will always yield identical numbers ($T=0$ determinism), eliminating LLM hallucination and grading variance.

### 5.2 Why Hybrid Skill Matching (Taxonomy + Curated Relations + High-Threshold Embedding)?
- Pure keyword search fails on synonyms (`Postgres` vs `PostgreSQL`).
- Pure embeddings fail on technical specificity (e.g. word embeddings often report high similarity between unrelated databases like `Redis` and `PostgreSQL` simply because both are storage engines).
- Our hybrid approach uses exact taxonomy aliasing first, explicit curated relationships second, and restricts embeddings to $\ge 0.75$ cosine fallback.

### 5.3 Why Chunk-Level Semantic Similarity?
- Averaging entire resume text vectors washes out specific technical achievements.
- Paragraph-level or document-level cosine scores suffer from length bias (longer resumes score artificially low).
- Comparing JD requirements against individual work sentences via top-$k$ maximum pooling accurately captures whether the candidate performed the required tasks.

---

## 6. Known Limitations

1. **Scanned & Image Resumes**: Resumes consisting solely of scanned bitmaps with no text layer cannot be parsed without OCR. The system reports an explicit `parse_status: failed` error rather than crashing.
2. **Taxonomy Scope & Untaxonomized Domains**: For domains without explicit taxonomy coverage or curated relationship entries, skill matching depends on exact/alias matches plus an embedding fallback with a strict threshold of cosine $\ge 0.75$ on short skill names. As a result, paraphrased skills (e.g. "Newsletter marketing" for "Email Marketing", "Split testing" for "A/B Testing") may receive no skill credit even though the holistic semantic component still recognizes the alignment in work history.
3. **Listed-Only Skills & Keyword Stuffing**: Skills that appear only in a resume's skills list retain partial credit ($0.50$ credit multiplier). Consequently, a keyword stuffer listing numerous unverified skills can occasionally outscore an honest candidate from a completely different domain; the system's keyword stuffing badge (`KEYWORD_STUFFING`) flags this behavior when $\ge 8$ matched skills are listed-only, comprising $\ge 70\%$ of matches with $< 2$ demonstrated skills.
4. **Single Generic Skill in Role Relevance**: Under the 3-tier role relevance rule, demonstrating $\ge 1$ JD skill in a role's title or bullets awards Tier 0.5 (half-credit) for that tenure. If that single demonstrated skill is an ubiquitous, generic skill (such as `SQL` in a Digital Marketing JD, or `Git`/`REST APIs` in backend engineering), an applicant from an unrelated technical field (e.g. a software engineer with `SQL`) can earn 50% relevance tenure for a non-technical or differently focused role.
5. **Strict Date Parsing**: If a resume omits dates entirely, non-overlapping experience resolves to 0.0 years.
