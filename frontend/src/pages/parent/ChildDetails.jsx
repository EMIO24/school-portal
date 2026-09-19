import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import api from '../../services/api';
import MyResult from '../student/MyResult';
import Fees from '../student/Fees';

export default function ChildDetails({ mode }) {
  const { studentId } = useParams();
  const [child, setChild] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    setLoading(true); setError(''); setChild(null);
    api.get('/api/parent/children/').then(({ data }) => {
      if (!active) return;
      const found = data.find(item => String(item.student_id) === studentId);
      if (found) setChild(found);
      else setError('This student is not linked to your parent account.');
    }).catch(() => { if (active) setError('Could not load your child. Please try again.'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [studentId]);
  return <>
    <Link to="/parent/dashboard">Back to children</Link>
    {loading && <p role="status">Loading student...</p>}
    {error && <p role="alert">{error}</p>}
    {child && <>
      <h1>{child.name}</h1>
      {mode === 'results' ? <MyResult studentId={child.user_id} /> : <Fees studentId={child.student_id} />}
    </>}
  </>;
}
