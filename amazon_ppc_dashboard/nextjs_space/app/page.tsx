export default function Home() {
  return (
    <div style={{ 
      height: '100vh', 
      width: '100vw', 
      margin: 0, 
      padding: 0,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: 'system-ui, -apple-system, sans-serif',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      color: 'white'
    }}>
      <div style={{
        background: 'white',
        color: '#333',
        padding: '40px',
        borderRadius: '15px',
        boxShadow: '0 10px 40px rgba(0,0,0,0.2)',
        maxWidth: '600px',
        textAlign: 'center'
      }}>
        <h1 style={{ color: '#667eea', marginBottom: '20px' }}>
          🚀 Amazon PPC Optimizer Dashboard
        </h1>
        <p style={{ fontSize: '18px', lineHeight: '1.6', marginBottom: '20px' }}>
          Dashboard API is active and ready to receive optimization data.
        </p>
        <div style={{
          background: '#f0f0f0',
          padding: '20px',
          borderRadius: '8px',
          marginBottom: '20px',
          textAlign: 'left'
        }}>
          <p style={{ margin: '10px 0' }}><strong>✅ API Endpoints:</strong></p>
          <ul style={{ margin: '10px 0 10px 20px', lineHeight: '1.8' }}>
            <li>/api/health</li>
            <li>/api/optimization-status</li>
            <li>/api/optimization-results</li>
            <li>/api/optimization-error</li>
          </ul>
        </div>
        <p style={{ fontSize: '14px', color: '#666' }}>
          The optimizer will automatically send data to these endpoints after each run.
        </p>
      </div>
    </div>
  );
}
