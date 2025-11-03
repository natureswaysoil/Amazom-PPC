export default function Home() {
  // Cloud Run proxy and location; you can also pull from NEXT_PUBLIC env vars if preferred
  const proxy = encodeURIComponent('https://bq-proxy-1009540130231.us-east4.run.app');
  const location = encodeURIComponent('us-east4');

  // The dashboard is hosted on GitHub Pages; we pass proxy + location to auto-connect
  const src = `https://natureswaysoil.github.io/best/?proxy=${proxy}&location=${location}`;

  return (
    <div style={{ height: '100vh', width: '100vw', margin: 0, padding: 0 }}>
      <iframe
        src={src}
        title="Amazon PPC Dashboard"
        style={{ border: 0, width: '100%', height: '100%' }}
        allow="clipboard-read; clipboard-write"
      />
    </div>
  );
}
