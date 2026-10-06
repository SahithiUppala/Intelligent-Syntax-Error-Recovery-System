import ErrorBoundary from './components/ErrorBoundary.jsx'
import Home from './pages/Home.jsx'

function App() {
  return (
    <ErrorBoundary>
      <Home />
    </ErrorBoundary>
  )
}

export default App
