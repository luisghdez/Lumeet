import React, { useState } from 'react';
import { LayoutDashboard, Users, MessageSquare, Plus, Video } from 'lucide-react';
import ApplicantCard from './components/ApplicantCard';
import CreateSection from './components/CreateSection';
import VariantLab from './components/VariantLab';

function App() {
  const [activeTab, setActiveTab] = useState('recruit');

  const navItems = [
    // { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'recruit', label: 'Recruit', icon: Users },
    // { id: 'messages', label: 'Messages', icon: MessageSquare },
    { id: 'create', label: 'Create', icon: Plus },
    { id: 'variant-lab', label: 'Variant Lab', icon: Video },
  ];

  // Mock data for applicant cards
  const applicants = [
    {
      id: 1,
      name: 'Emma Thompson',
      avatar: 'https://i.pravatar.cc/150?img=1',
      university: 'Stanford University',
      location: 'Palo Alto, CA',
      bio: 'Passionate about mental health advocacy and creating supportive communities.',
      tags: ['Psychology', 'College Junior', 'Content Creator'],
      lastActive: '1d ago',
    },
    {
      id: 2,
      name: 'Marcus Chen',
      avatar: 'https://i.pravatar.cc/150?img=13',
      university: 'MIT',
      location: 'Cambridge, MA',
      bio: 'Tech enthusiast sharing coding tutorials and startup journey.',
      tags: ['Computer Science', 'Senior', 'Tech'],
      lastActive: '2h ago',
    },
    {
      id: 3,
      name: 'Sophia Rodriguez',
      avatar: 'https://i.pravatar.cc/150?img=5',
      university: 'UC Berkeley',
      location: 'Berkeley, CA',
      bio: 'Environmental activist and sustainable living content creator.',
      tags: ['Environmental Studies', 'Sophomore'],
      lastActive: '3d ago',
    },
    {
      id: 4,
      name: 'James Wilson',
      avatar: 'https://i.pravatar.cc/150?img=12',
      university: 'Harvard University',
      location: 'Cambridge, MA',
      bio: 'Business and finance YouTuber helping students build wealth.',
      tags: ['Business', 'MBA Candidate', 'Finance'],
      lastActive: '5h ago',
    },
    {
      id: 5,
      name: 'Aria Patel',
      avatar: 'https://i.pravatar.cc/150?img=9',
      university: 'Columbia University',
      location: 'New York, NY',
      bio: 'Fashion and lifestyle influencer with a focus on sustainable brands.',
      tags: ['Fashion Design', 'Senior'],
      lastActive: '1d ago',
    },
    {
      id: 6,
      name: 'Noah Kim',
      avatar: 'https://i.pravatar.cc/150?img=14',
      university: 'UCLA',
      location: 'Los Angeles, CA',
      bio: 'Film student and aspiring director sharing behind-the-scenes content.',
      tags: ['Film Studies', 'Junior', 'Filmmaker'],
      lastActive: '4h ago',
    },
  ];

  return (
    <div className="flex h-screen overflow-hidden relative">
      {/* Background blobs */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 -left-4 w-96 h-96 bg-purple-300 rounded-full mix-blend-multiply filter blur-3xl opacity-30" />
        <div className="absolute top-0 -right-4 w-96 h-96 bg-pink-300 rounded-full mix-blend-multiply filter blur-3xl opacity-30" />
        <div className="absolute -bottom-8 left-20 w-96 h-96 bg-blue-300 rounded-full mix-blend-multiply filter blur-3xl opacity-30" />
      </div>

      {/* Sidebar */}
      <aside className="relative z-10 w-64 flex-shrink-0 p-6 glass-heavy border-r border-white/30">
        <div className="mb-12">
          <h1 className="text-3xl font-bold bg-gradient-to-r from-purple-600 via-purple-500 to-pink-500 bg-clip-text text-transparent">
            Lumeet
          </h1>
        </div>

        <nav className="space-y-3">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`
                  w-full flex items-center gap-3 px-4 py-3.5 rounded-2xl
                  ${
                    isActive
                      ? 'glass-card border border-purple-300/50 text-purple-700'
                      : 'text-gray-700'
                  }
                `}
              >
                <Icon size={20} strokeWidth={isActive ? 2.5 : 2} />
                <span className="font-semibold">{item.label}</span>
                {item.showPlus && (
                  <span className="ml-auto text-lg font-bold">+</span>
                )}
              </button>
            );
          })}
        </nav>
      </aside>

      {/* Main Content */}
      <main className="relative z-10 flex-1 overflow-y-auto p-8">
        {activeTab === 'create' ? (
          <CreateSection />
        ) : activeTab === 'variant-lab' ? (
          <VariantLab />
        ) : (
          <div className="max-w-7xl mx-auto">
            {/* Header */}
            <div className="mb-8 text-center">
              <h2 className="text-4xl font-bold text-gray-900 mb-2">Creator Applicants</h2>
              <p className="text-gray-700 text-lg">Review and connect with talented creators</p>
            </div>

            {/* Applicants Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {applicants.map((applicant) => (
                <ApplicantCard key={applicant.id} applicant={applicant} />
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;

