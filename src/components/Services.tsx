const Services = () => {
  const services = [
    "Comprehensive vehicle inspections",
    "Affordable and flexible financing options",
    "Long-term extended warranty plans",
    "24/7 customer support",
    "Expert guidance and advice"
  ]

  return (
    <section className="py-20 bg-black">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-12 items-center">
          {/* Text Side */}
          <div>
            <ul className="space-y-4 mb-8">
              {services.map((service) => (
                <li key={service} className="flex items-start">
                  <svg className="w-6 h-6 text-amber-600 mr-3 flex-shrink-0 mt-1" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span className="text-white text-lg">{service}</span>
                </li>
              ))}
            </ul>
            <button className="border-2 border-white text-white hover:bg-white hover:text-black px-8 py-3 rounded-lg font-medium transition-colors">
              Start Now
            </button>
          </div>
          
          {/* Image Side */}
          <div>
            <div className="relative h-96 rounded-lg overflow-hidden shadow-xl">
              <img 
                src="/images/pexels-clement-proust-363898785-14558135.jpg" 
                alt="Sports cars on race track" 
                className="w-full h-full object-cover"
              />
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

export default Services

