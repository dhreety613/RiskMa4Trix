import { Route, Routes } from 'react-router-dom'
import Company from './pages/Company'
import Home from './pages/Home'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/company/:ticker" element={<Company />} />
    </Routes>
  )
}

export default App
