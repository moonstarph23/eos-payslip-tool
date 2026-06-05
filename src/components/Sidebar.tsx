import React from 'react';

interface SidebarProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
}

const Sidebar: React.FC<SidebarProps> = ({ activeTab, onTabChange }) => {
  const navItems = [
    { id: 'external', label: 'Split PDF', icon: 'upload_file' },
    { id: 'internal', label: 'Run Excel Macro Template', icon: 'business_center' },
    { id: 'encrypt', label: 'Encrypt Payslips', icon: 'lock' },
    { id: 'email', label: 'Email Distribution', icon: 'mail' },
    { id: 'settings', label: 'Settings', icon: 'settings' },
  ];

  return (
    <aside className="fixed left-0 top-0 h-full w-sidebar-width bg-on-secondary-fixed shadow-xl flex flex-col z-50">
      {/* Logo Section */}
      <div className="p-8">
        <div className="flex items-center gap-3 mb-10">
          <div className="w-10 h-10 bg-primary-container rounded-lg flex items-center justify-center">
            <span className="material-symbols-outlined text-white">account_balance_wallet</span>
          </div>
          <div>
            <h1 className="font-headline text-headline-md font-bold text-surface-container-lowest leading-none">
              EOS Payslip
            </h1>
            <p className="text-text-muted text-xs mt-1">Payroll Professional</p>
          </div>
        </div>
        
        {/* Navigation */}
        <nav className="space-y-1">
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => onTabChange(item.id)}
              className={`w-full nav-item ${
                activeTab === item.id
                  ? 'active-nav'
                  : 'nav-item-inactive'
              }`}
            >
              <span className={`material-symbols-outlined ${
                activeTab === item.id ? 'text-primary-fixed-dim' : 'group-hover:text-primary-fixed-dim'
              }`}>
                {item.icon}
              </span>
              <span className="font-label text-label-md">{item.label}</span>
            </button>
          ))}
        </nav>
      </div>
      

    </aside>
  );
};

export default Sidebar;
