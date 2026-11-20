"""Unit tests for skills extraction and taxonomy matching."""

from app.services.skills import get_skills_service


def test_extract_canonical_skills():
    """Verify phrase matcher extracts canonical skills from text."""
    service = get_skills_service()
    text = "We need an engineer experienced with Python, FastAPI, and Docker."
    skills = service.extract_skills(text)

    assert "Python" in skills
    assert "FastAPI" in skills
    assert "Docker" in skills


def test_alias_normalization():
    """Verify aliases correctly map to canonical skill names."""
    service = get_skills_service()

    assert service.get_canonical_name("postgres") == "PostgreSQL"
    assert service.get_canonical_name("psql") == "PostgreSQL"
    assert service.get_canonical_name("k8s") == "Kubernetes"
    assert service.get_canonical_name("python 3") == "Python"
    assert service.get_canonical_name("fast api") == "FastAPI"


def test_phrase_matching_with_aliases_in_text():
    """Verify alias phrases in text extract the canonical skill."""
    service = get_skills_service()
    text = "Built services with python 3, deployed on k8s with postgres database and github actions."
    skills = service.extract_skills(text)

    assert "Python" in skills
    assert "Kubernetes" in skills
    assert "PostgreSQL" in skills
    assert "CI/CD" in skills


def test_skills_deduplication():
    """Verify skills mentioned multiple times are deduplicated."""
    service = get_skills_service()
    text = "Python python PYTHON Python3 py FastAPI FastAPI"
    skills = service.extract_skills(text)

    assert skills.count("Python") == 1
    assert skills.count("FastAPI") == 1


def test_category_lookup():
    """Verify taxonomy categories can be retrieved."""
    service = get_skills_service()
    assert service.get_skill_category("Python") == "Languages"
    assert service.get_skill_category("FastAPI") == "Backend Frameworks"
    assert service.get_skill_category("Docker") == "Cloud & DevOps"


def test_java_ecosystem_skills():
    """Verify Java ecosystem skills are recognized as distinct canonical entities."""
    service = get_skills_service()
    text = (
        "Required: Java, Spring Boot, Hibernate, JPA, JUnit, Mockito, Maven, "
        "Gradle, Kafka, RabbitMQ, Jenkins, Kotlin, Struts, JDBC, Oracle, "
        "Spring MVC, Spring Data JPA."
    )
    extracted = set(service.extract_skills(text))
    expected = {
        "Java", "Spring Boot", "Hibernate", "JPA", "JUnit", "Mockito", "Maven",
        "Gradle", "Kafka", "RabbitMQ", "Jenkins", "Kotlin", "Struts", "JDBC",
        "Oracle", "Spring MVC", "Spring Data JPA"
    }
    assert expected.issubset(extracted), f"Missing: {expected - extracted}"


def test_java_aliases_and_related_credit():
    """Verify aliases and curated related-skill credits for Java ecosystem."""
    service = get_skills_service()

    # Aliases
    assert service.get_canonical_name("RESTful web services") == "REST APIs"
    assert service.get_canonical_name("springboot") == "Spring Boot"
    assert service.get_canonical_name("spring-boot") == "Spring Boot"
    assert service.get_canonical_name("apache kafka") == "Kafka"
    assert service.get_canonical_name("apache maven") == "Maven"

    # Related skills credit
    assert service.get_curated_related_credit("Spring Boot", "Spring Framework") == 0.60
    assert service.get_curated_related_credit("JPA", "Hibernate") == 0.80
    assert service.get_curated_related_credit("Hibernate", "JPA") == 0.80
    assert service.get_curated_related_credit("Kafka", "RabbitMQ") == 0.70
    assert service.get_curated_related_credit("Kafka", "Message Queues") == 0.80
    assert service.get_curated_related_credit("RabbitMQ", "Message Queues") == 0.80


def test_data_science_taxonomy_and_token_flow():
    """Verify Data Science skills, aliases, and curated credits in taxonomy."""
    service = get_skills_service()

    # Canonical name mapping
    assert service.get_canonical_name("scikit-learn") == "scikit-learn"
    assert service.get_canonical_name("sklearn") == "scikit-learn"
    assert service.get_canonical_name("numpy") == "NumPy"
    assert service.get_canonical_name("np") == "NumPy"
    assert service.get_canonical_name("pytorch") == "PyTorch"
    assert service.get_canonical_name("torch") == "PyTorch"
    assert service.get_canonical_name("tensorflow") == "TensorFlow"
    assert service.get_canonical_name("tf") == "TensorFlow"
    assert service.get_canonical_name("keras") == "Keras"
    assert service.get_canonical_name("xgboost") == "XGBoost"
    assert service.get_canonical_name("xgb") == "XGBoost"
    assert service.get_canonical_name("matplotlib") == "Matplotlib"
    assert service.get_canonical_name("seaborn") == "Seaborn"
    assert service.get_canonical_name("tableau") == "Tableau"
    assert service.get_canonical_name("power bi") == "Power BI"
    assert service.get_canonical_name("powerbi") == "Power BI"
    assert service.get_canonical_name("spark") == "Spark"
    assert service.get_canonical_name("pyspark") == "Spark"
    assert service.get_canonical_name("mlflow") == "MLflow"
    assert service.get_canonical_name("statistics") == "Statistics"

    # Curated Related Skills credit
    assert service.get_curated_related_credit("Machine Learning", "scikit-learn") == 0.70
    assert service.get_curated_related_credit("scikit-learn", "Machine Learning") == 0.70
    assert service.get_curated_related_credit("PyTorch", "TensorFlow") == 0.70
    assert service.get_curated_related_credit("TensorFlow", "PyTorch") == 0.70
    assert service.get_curated_related_credit("Pandas", "NumPy") == 0.40
    assert service.get_curated_related_credit("NumPy", "Pandas") == 0.40
    assert service.get_curated_related_credit("Tableau", "Power BI") == 0.80
    assert service.get_curated_related_credit("Power BI", "Tableau") == 0.80
    assert service.get_curated_related_credit("SciPy", "NumPy") == 0.60
    assert service.get_curated_related_credit("NumPy", "SciPy") == 0.60



