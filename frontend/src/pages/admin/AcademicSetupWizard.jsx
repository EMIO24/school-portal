import React, { useEffect, useMemo, useState } from 'react';
import api from '../../services/api';

const STEP_META = [
  { key: 'academic_session', label: 'Academic Session', url: '/admin/calendar' },
  { key: 'terms', label: 'Terms', url: '/admin/calendar' },
  { key: 'classes_and_arms', label: 'Classes & Arms', url: '/admin/students' },
  { key: 'subjects', label: 'Subjects', url: '/admin/subjects' },
  { key: 'teachers', label: 'Teachers', url: '/admin/staff' },
  { key: 'teacher_assignments', label: 'Teacher Assignments', url: '/admin/subject-assignments' },
  { key: 'assessment_structure', label: 'Assessment Structure', url: '/admin/subjects' },
  { key: 'grading_system', label: 'Grading System', url: '/admin/results' },
];

export default function AcademicSetupWizard() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;

    api.get('/api/school/setup-status/')
      .then(({ data }) => {
        if (!active) return;
        const steps = Array.isArray(data.steps) ? data.steps : STEP_META.map((step) => ({
          key: step.key,
          title: step.label,
          description: '',
          done: false,
          link: step.url,
        }));

        setStatus({ ...data, steps });
      })
      .catch(() => {
        if (active) setError('We could not load the setup guidance right now.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => { active = false; };
  }, []);

  const steps = useMemo(() => {
    if (!status?.steps) return STEP_META.map((step, index) => ({
      key: step.key,
      title: step.label,
      description: 'Complete this setup step to continue.',
      done: false,
      link: step.url,
      index: index + 1,
    }));

    return status.steps.map((step, index) => ({ ...step, index: index + 1, title: step.title || STEP_META[index]?.label || `Step ${index + 1}` }));
  }, [status]);

  const completed = steps.filter((step) => step.done).length;
  const percent = Math.round((completed / steps.length) * 100) || 0;

  return (
    <main className="page-shell" style={{ maxWidth: 1100, margin: '0 auto', padding: '32px 20px 48px' }}>
      <h1 className="page-title" style={{ marginBottom: 8 }}>Academic Setup Wizard</h1>
      <p className="page-subtitle" style={{ marginTop: 0, marginBottom: 24, color: 'var(--muted)' }}>
        Follow the school setup in order. Each step is designed to be understandable without needing database knowledge.
      </p>

      {error && <p role="alert" style={{ color: 'var(--danger, #b42318)', marginBottom: 16 }}>{error}</p>}

      {loading ? (
        <p>Loading setup progress…</p>
      ) : (
        <>
          <div style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 16, padding: 20, marginBottom: 24 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
              <div>
                <strong style={{ fontSize: 18 }}>Setup progress</strong>
                <div style={{ color: 'var(--muted)' }}>{completed} of {steps.length} steps complete</div>
              </div>
              <div style={{ fontWeight: 700, fontSize: 18 }}>{percent}%</div>
            </div>
            <div style={{ marginTop: 16, height: 12, background: 'var(--surface)', borderRadius: 999, overflow: 'hidden' }}>
              <div style={{ width: `${percent}%`, height: '100%', background: 'linear-gradient(90deg, var(--primary), var(--secondary))', transition: 'width 0.2s ease' }} />
            </div>
          </div>

          <ol style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: 16 }}>
            {steps.map((step) => {
              const isDone = !!step.done;
              return (
                <li key={step.key}>
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '56px minmax(0, 1fr) auto',
                      gap: 18,
                      alignItems: 'center',
                      background: isDone ? 'rgba(26, 107, 60, 0.08)' : 'var(--panel)',
                      border: `1px solid ${isDone ? 'rgba(26,107,60,0.35)' : 'var(--border)'}`,
                      borderRadius: 16,
                      padding: '16px 18px',
                    }}
                  >
                    <div
                      aria-label={isDone ? `${step.title} complete` : `${step.title} not complete`}
                      style={{
                        width: 36,
                        height: 36,
                        borderRadius: '50%',
                        display: 'grid',
                        placeItems: 'center',
                        background: isDone ? 'var(--primary)' : 'var(--surface)',
                        color: isDone ? '#fff' : 'var(--muted)',
                        fontWeight: 700,
                        border: `1px solid ${isDone ? 'var(--primary)' : 'var(--border)'}`,
                      }}
                    >
                      {isDone ? '✓' : step.index}
                    </div>

                    <div>
                      <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>{step.title}</div>
                      <div style={{ color: 'var(--muted)' }}>{step.description || 'Complete this step to move on to the next part of the school setup.'}</div>
                    </div>

                    <div>
                      {step.link ? (
                        <a
                          href={step.link}
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            padding: '8px 12px',
                            borderRadius: 10,
                            border: '1px solid var(--border)',
                            background: isDone ? 'var(--primary)' : 'transparent',
                            color: isDone ? '#fff' : 'var(--text)',
                            fontWeight: 600,
                            textDecoration: 'none',
                          }}
                        >
                          {isDone ? 'Review' : 'Open'}
                        </a>
                      ) : (
                        <span style={{ fontWeight: 600, color: isDone ? 'var(--success)' : 'var(--muted)' }}>
                          {isDone ? 'Complete' : 'Pending'}
                        </span>
                      )}
                    </div>
                  </div>
                </li>
              );
            })}
          </ol>

          {status?.wizard_ready && (
            <div style={{ marginTop: 28, padding: 18, border: '1px solid rgba(26,107,60,0.35)', borderRadius: 14, background: 'rgba(26,107,60,0.06)' }}>
              <strong style={{ fontSize: 18 }}>School setup is ready.</strong>
              <div style={{ marginTop: 8, color: 'var(--muted)' }}>All core academic tasks have been configured and the school can begin onboarding learners and staff.</div>
            </div>
          )}
        </>
      )}
    </main>
  );
}
