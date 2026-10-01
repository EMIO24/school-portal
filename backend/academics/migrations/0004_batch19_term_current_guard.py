# Batch 19 final hardening: database guard for one current term per school.

from django.db import migrations


CREATE_SQL = r"""
CREATE OR REPLACE FUNCTION academics_enforce_one_current_term_per_school()
RETURNS trigger AS $$
DECLARE
    school_pk bigint;
BEGIN
    IF NEW.is_current IS DISTINCT FROM TRUE THEN
        RETURN NEW;
    END IF;

    SELECT school_id INTO school_pk
    FROM academics_academicsession
    WHERE id = NEW.session_id;

    IF school_pk IS NULL THEN
        RETURN NEW;
    END IF;

    -- Serialize current-calendar changes for this school.
    PERFORM 1 FROM tenants_school WHERE id = school_pk FOR UPDATE;

    IF EXISTS (
        SELECT 1
        FROM academics_term t
        JOIN academics_academicsession s ON s.id = t.session_id
        WHERE s.school_id = school_pk
          AND t.is_current = TRUE
          AND t.id <> COALESCE(NEW.id, 0)
    ) THEN
        RAISE EXCEPTION 'Only one current academic term is allowed per school.'
            USING ERRCODE = '23505';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS academics_one_current_term_per_school ON academics_term;
CREATE TRIGGER academics_one_current_term_per_school
BEFORE INSERT OR UPDATE OF is_current, session_id
ON academics_term
FOR EACH ROW
EXECUTE FUNCTION academics_enforce_one_current_term_per_school();
"""

DROP_SQL = r"""
DROP TRIGGER IF EXISTS academics_one_current_term_per_school ON academics_term;
DROP FUNCTION IF EXISTS academics_enforce_one_current_term_per_school();
"""


def normalize_current_terms(apps, schema_editor):
    Term = apps.get_model("academics", "Term")
    AcademicSession = apps.get_model("academics", "AcademicSession")
    School = apps.get_model("tenants", "School")

    for school_id in School.objects.values_list("pk", flat=True).iterator():
        current_ids = list(
            Term.objects.filter(
                session__school_id=school_id,
                is_current=True,
            )
            .order_by("-session__start_date", "-start_date", "-pk")
            .values_list("pk", flat=True)
        )
        if len(current_ids) > 1:
            Term.objects.filter(pk__in=current_ids[1:]).update(is_current=False)


def create_postgres_guard(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(CREATE_SQL)


def drop_postgres_guard(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(DROP_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ("academics", "0003_academic_rollover_safety"),
    ]

    operations = [
        migrations.RunPython(normalize_current_terms, migrations.RunPython.noop),
        migrations.RunPython(create_postgres_guard, drop_postgres_guard),
    ]
