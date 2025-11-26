import { useChatbot } from '../contexts/ChatbotContext'

const About = () => {
  const { openFullPageChatbot } = useChatbot()

  return (
    <section className="py-20 bg-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-12 items-center">
          {/* Image Side */}
          <div className="order-2 md:order-1">
            <div className="relative h-96 rounded-lg overflow-hidden shadow-xl">
              <img 
                src="/images/pexels-hazardos-804128 copy.jpg" 
                alt="Man checking smartphone in modern car interior" 
                className="w-full h-full object-cover"
              />
            </div>
          </div>
          
          {/* Text Side */}
          <div className="order-1 md:order-2">
            <h2 className="text-4xl md:text-5xl font-bold text-black mb-6">
              Auto Emporium
            </h2>
            <p className="text-lg text-gray-700 mb-8 leading-relaxed">
              At Auto Emporium, we pride ourselves on great service, competitive prices, and a hassle-free buying experience. Let us guide you to your perfect automotive match and make your driving dreams a reality.
            </p>
            <button
              onClick={openFullPageChatbot}
              className="bg-amber-600 hover:bg-amber-700 text-white px-8 py-3 rounded-lg font-medium transition-colors"
            >
              Start Now
            </button>
          </div>
        </div>
      </div>
    </section>
  )
}

export default About

