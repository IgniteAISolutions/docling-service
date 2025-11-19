import React from 'react'
import './App.css'
import UniversalUploader from './components/UniversalUploader'

function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto px-4 py-8">
        <header className="text-center mb-8">
          <h1 className="text-3xl font-semibold text-gray-900 mb-2">
            Harts of Stur Product Automation
          </h1>
          <p className="text-gray-600">
            Transform product catalogs into Business Central-ready descriptions
          </p>
        </header>
        <UniversalUploader />
      </div>
    </div>
  )
}

export default App
