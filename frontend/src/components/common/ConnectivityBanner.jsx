import React, { useEffect, useState } from 'react';

export default function ConnectivityBanner() {
  const [online, setOnline] = useState(() => navigator.onLine);
  const [recovered, setRecovered] = useState(false);
  useEffect(() => {
    const wentOffline = () => { setOnline(false); setRecovered(false); };
    const wentOnline = () => { setOnline(true); setRecovered(true); };
    window.addEventListener('offline', wentOffline);
    window.addEventListener('online', wentOnline);
    return () => {
      window.removeEventListener('offline', wentOffline);
      window.removeEventListener('online', wentOnline);
    };
  }, []);
  useEffect(() => {
    if (!recovered) return undefined;
    const timer = setTimeout(() => setRecovered(false), 5000);
    return () => clearTimeout(timer);
  }, [recovered]);
  if (online && !recovered) return null;
  return <div className={'connectivity-banner ' + (online ? 'is-recovered' : 'is-offline')} role="status" aria-live="polite">
    {online ? 'Connection restored. Check your work before continuing.' : "You're offline. Some actions may be unavailable until your connection returns."}
  </div>;
}
