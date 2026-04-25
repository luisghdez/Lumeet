import React, { useEffect, useState, useCallback } from 'react';
import {
  LayoutDashboard,
  Users,
  MessageSquare,
  Plus,
  Video,
  Film,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import ApplicantCard from './components/ApplicantCard';
import CreateSection from './components/CreateSection';
import VariantLab from './components/VariantLab';
import VideoLibrary from './components/VideoLibrary';
import GenerationCenter from './components/GenerationCenter';
import ScheduleModal from './components/ScheduleModal';
import ScheduledPosts from './components/ScheduledPosts';
import Wordmark from './components/ui/Wordmark';

const SIDEBAR_COLLAPSED_KEY = 'lumeet-sidebar-collapsed';

function App() {
  const [activeTab, setActiveTab] = useState('create');
  const [scheduleTarget, setScheduleTarget] = useState(null);
  const [genRefreshKey, setGenRefreshKey] = useState(0);
  const [genFocusKey, setGenFocusKey] = useState(0);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try {
      return window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === '1';
    } catch {
      return false;
    }
  });

  const handleScheduleFromCenter = useCallback((generation) => {
    setScheduleTarget(generation);
  }, []);

  const handleScheduled = useCallback(() => {
    // Bump key so GenerationCenter re-fetches and sees the scheduled flag
    setGenRefreshKey((k) => k + 1);
  }, []);

  const handleVideoGenerationStarted = useCallback(() => {
    setGenFocusKey((k) => k + 1);
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('late_connected') === '1') {
      setActiveTab('create');
    }
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem(SIDEBAR_COLLAPSED_KEY, sidebarCollapsed ? '1' : '0');
    } catch {
      /* ignore */
    }
  }, [sidebarCollapsed]);

  const navItems = [
    // { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    // { id: 'recruit', label: 'Recruit', icon: Users },
    // { id: 'messages', label: 'Messages', icon: MessageSquare },
    { id: 'create', label: 'Create', icon: Plus },
    // { id: 'variant-lab', label: 'Variant Lab', icon: Video },
    { id: 'video-library', label: 'Library', icon: Film },
    { id: 'scheduled', label: 'Scheduled', icon: CalendarDays },
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
      {/* Generation Center – top-right floating button */}
      <GenerationCenter
        onSchedule={handleScheduleFromCenter}
        refreshKey={genRefreshKey}
        focusKey={genFocusKey}
      />

      {/* Schedule Modal – opened from Generation Center */}
      {scheduleTarget && (
        <ScheduleModal
          generation={scheduleTarget}
          onClose={() => setScheduleTarget(null)}
          onScheduled={handleScheduled}
        />
      )}

      {/* Atmospheric drift orb — soft accent over the cloudscape body backdrop. */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 -right-24 w-[28rem] h-[28rem] rounded-full bg-white/40 blur-3xl animate-drift-slow" />
        <div className="absolute -bottom-32 left-10 w-[32rem] h-[32rem] rounded-full bg-nimbus-300/30 blur-3xl animate-drift" />
      </div>

      {/* Sidebar — collapsible to an icon rail (desktop only) */}
      <aside
        className={`relative z-10 hidden md:flex md:flex-shrink-0 flex-col glass-pane border-r border-white/40 transition-[width,padding] duration-300 ease-out overflow-hidden ${
          sidebarCollapsed ? 'w-[4.5rem] px-2 py-6 items-center' : 'w-64 p-6'
        }`}
      >
        <div
          className={`mb-8 w-full flex shrink-0 ${
            sidebarCollapsed ? 'flex-col items-center gap-3' : 'items-start justify-between gap-2'
          }`}
        >
          {!sidebarCollapsed && (
            <div className="min-w-0 flex-1">
              <p className="text-[10px] uppercase tracking-[0.22em] text-nimbus-600 font-medium mb-2">
                Workspace
              </p>
              <Wordmark size="lg" />
            </div>
          )}
          <button
            type="button"
            onClick={() => setSidebarCollapsed((c) => !c)}
            className="flex-shrink-0 p-2 rounded-full text-nimbus-700 hover:bg-white/40 transition-colors"
            aria-expanded={!sidebarCollapsed}
            aria-controls="app-sidebar-nav"
            aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {sidebarCollapsed ? (
              <ChevronRight size={18} strokeWidth={2} aria-hidden />
            ) : (
              <ChevronLeft size={18} strokeWidth={2} aria-hidden />
            )}
          </button>
        </div>

        <nav id="app-sidebar-nav" className={`space-y-2 flex-1 w-full ${sidebarCollapsed ? 'flex flex-col items-center' : ''}`}>
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                title={sidebarCollapsed ? item.label : undefined}
                aria-current={isActive ? 'page' : undefined}
                className={`flex items-center rounded-full transition-colors duration-200 touch-manipulation ${
                  sidebarCollapsed
                    ? `justify-center w-11 h-11 p-0 ${
                        isActive
                          ? 'bg-ink-950 text-white shadow-pill'
                          : 'text-nimbus-700 hover:bg-white/40'
                      }`
                    : `w-full gap-3 px-4 py-3 ${
                        isActive
                          ? 'bg-ink-950 text-white shadow-pill'
                          : 'text-nimbus-700 hover:bg-white/40'
                      }`
                }`}
              >
                <Icon size={18} strokeWidth={isActive ? 2.25 : 2} aria-hidden />
                {!sidebarCollapsed && (
                  <>
                    <span className="font-medium tracking-tight">{item.label}</span>
                    {item.showPlus && (
                      <span className="ml-auto text-lg font-bold">+</span>
                    )}
                  </>
                )}
              </button>
            );
          })}
        </nav>

        <div
          className={`mt-6 pt-5 border-t border-white/40 w-full shrink-0 ${
            sidebarCollapsed ? 'flex justify-center' : ''
          }`}
        >
          <div
            className={`flex items-center gap-2.5 ${sidebarCollapsed ? 'px-0 justify-center' : 'px-1'}`}
            title={sidebarCollapsed ? 'All systems operational' : undefined}
          >
            <span className="relative flex h-2 w-2 shrink-0">
              <span className="absolute inline-flex h-full w-full rounded-full bg-emerald-400/70 animate-ping" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>
            {!sidebarCollapsed && (
              <span className="text-xs text-nimbus-700 font-medium tracking-tight">
                All systems operational
              </span>
            )}
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className={`relative z-10 flex-1 p-4 pb-24 md:p-8 md:pb-8 ${activeTab === 'create' ? 'overflow-y-hidden' : 'overflow-y-auto'}`}>
        <div className="md:hidden sticky top-0 z-20 py-2 mb-4">
          <Wordmark size="lg" />
        </div>
        {activeTab === 'create' ? (
          <CreateSection onVideoGenerationStarted={handleVideoGenerationStarted} />
        ) : activeTab === 'variant-lab' ? (
          <VariantLab />
        ) : activeTab === 'video-library' ? (
          <VideoLibrary />
        ) : activeTab === 'scheduled' ? (
          <ScheduledPosts />
        ) : (
          <div className="max-w-7xl mx-auto">
            {/* Header */}
            <div className="mb-10 text-center">
              <h2 className="font-display font-medium text-display-xs md:text-display-sm text-ink-950 tracking-tightest mb-3">
                Creator Applicants
              </h2>
              <p className="text-nimbus-700 text-base md:text-lg">
                Review and connect with talented creators
              </p>
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

      <nav
        className="fixed z-50 md:hidden left-0 right-0 bottom-0 px-3 pointer-events-none"
        style={{ paddingBottom: 'max(0.75rem, env(safe-area-inset-bottom, 0px))' }}
        aria-label="Primary"
      >
        <div className="pointer-events-auto max-w-lg mx-auto glass-ink rounded-full px-1 py-1 shadow-pill border border-white/10">
          <div className="flex items-stretch justify-between gap-0.5">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setActiveTab(item.id)}
                  aria-current={isActive ? 'page' : undefined}
                  className={`flex flex-1 min-w-0 flex-row items-center justify-center gap-1.5 py-2.5 px-2 sm:px-3 rounded-full transition-colors touch-manipulation active:scale-[0.98] ${
                    isActive
                      ? 'bg-white text-ink-950 shadow-sm'
                      : 'text-white/75 hover:text-white'
                  }`}
                >
                  <Icon size={17} strokeWidth={isActive ? 2.25 : 2} className="shrink-0" aria-hidden />
                  <span className="text-[11px] sm:text-xs font-medium tracking-tight truncate">
                    {item.label}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </nav>
    </div>
  );
}

export default App;

