const Hero = () => {
  return (
    <section className="relative h-screen flex items-center justify-center overflow-hidden">
      {/* Background Image */}
      <div className="absolute inset-0">
        <img 
          src="/images/pexels-pixabay-210019.jpg" 
          alt="Hero background" 
          className="w-full h-full object-cover"
        />
        <div className="absolute inset-0 bg-gradient-to-r from-black/40 to-transparent"></div>
      </div>
      
      {/* Content */}
      <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 w-full">
        <div className="flex flex-col md:flex-row items-center justify-between">
          {/* Text Content */}
          <div className="text-white mb-8 md:mb-0 md:w-1/2">
            <h2 className="text-6xl md:text-7xl lg:text-8xl font-bold mb-4 leading-tight">
              Drive<br />
              Your Dream
            </h2>
            <p className="text-xl md:text-2xl text-gray-200">
              Attain freedom in style with your new car!
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}

export default Hero

