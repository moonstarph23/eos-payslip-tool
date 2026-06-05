import React, { useState, useEffect } from 'react';
import { invoke } from '@tauri-apps/api/tauri';

interface Alias {
  email: string;
  display_name: string;
}

interface EmailAccount {
  email: string;
  app_password: string;
  aliases: Alias[];
}

const isValidEmail = (email: string): boolean => {
  const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return regex.test(email.trim());
};

const SettingsTab: React.FC = () => {
  const [accounts, setAccounts] = useState<EmailAccount[]>([]);
  const [loading, setLoading] = useState(true);
  
  // Add account form
  const [newAccountEmail, setNewAccountEmail] = useState('');
  const [newAccountError, setNewAccountError] = useState('');
  
  // Add alias form (per account)
  const [activeAccount, setActiveAccount] = useState<string | null>(null);
  const [newAliasEmail, setNewAliasEmail] = useState('');
  const [newAliasName, setNewAliasName] = useState('');
  const [newAliasError, setNewAliasError] = useState('');

  // Load accounts from file on mount
  useEffect(() => {
    const loadAccounts = async () => {
      try {
        const result = await invoke<EmailAccount[]>('get_email_accounts');
        if (Array.isArray(result)) {
          setAccounts(result.filter((a) => a.email && a.email.includes('@')));
        }
      } catch (err) {
        console.error('Failed to load accounts:', err);
      } finally {
        setLoading(false);
      }
    };
    loadAccounts();
  }, []);

  const persistAccounts = async (updatedAccounts: EmailAccount[]) => {
    try {
      await invoke('save_email_accounts', { accounts: updatedAccounts });
    } catch (err) {
      console.error('Failed to save accounts:', err);
    }
  };

  const handleAddAccount = async () => {
    const trimmed = newAccountEmail.trim().toLowerCase();
    if (!trimmed) {
      setNewAccountError('Please enter an email address');
      return;
    }
    if (!isValidEmail(trimmed)) {
      setNewAccountError('Please enter a valid email address');
      return;
    }
    if (accounts.some((a) => a.email === trimmed)) {
      setNewAccountError('This account already exists');
      return;
    }
    const updated = [...accounts, { email: trimmed, app_password: '', aliases: [] as Alias[] }];
    setAccounts(updated);
    setNewAccountEmail('');
    setNewAccountError('');
    setActiveAccount(trimmed);
    await persistAccounts(updated);
  };

  const handleRemoveAccount = async (email: string) => {
    const updated = accounts.filter((a) => a.email !== email);
    setAccounts(updated);
    if (activeAccount === email) {
      setActiveAccount(null);
    }
    await persistAccounts(updated);
  };

  const handleAddAlias = async (accountEmail: string) => {
    const trimmedEmail = newAliasEmail.trim().toLowerCase();
    const trimmedName = newAliasName.trim();
    if (!trimmedEmail) {
      setNewAliasError('Please enter an alias email');
      return;
    }
    if (!isValidEmail(trimmedEmail)) {
      setNewAliasError('Please enter a valid email address');
      return;
    }

    const account = accounts.find((a) => a.email === accountEmail);
    if (account && account.aliases.some((al) => al.email === trimmedEmail)) {
      setNewAliasError('This alias already exists');
      return;
    }

    const updated = accounts.map((a) => {
      if (a.email === accountEmail) {
        return { ...a, aliases: [...a.aliases, { email: trimmedEmail, display_name: trimmedName }] };
      }
      return a;
    });
    setAccounts(updated);
    setNewAliasEmail('');
    setNewAliasName('');
    setNewAliasError('');
    await persistAccounts(updated);
  };

  const handleRemoveAlias = async (accountEmail: string, aliasEmail: string) => {
    const updated = accounts.map((a) => {
      if (a.email === accountEmail) {
        return { ...a, aliases: a.aliases.filter((al) => al.email !== aliasEmail) };
      }
      return a;
    });
    setAccounts(updated);
    await persistAccounts(updated);
  };

  const handleAccountKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAddAccount();
    }
  };

  const handleAliasKeyDown = (e: React.KeyboardEvent, accountEmail: string) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleAddAlias(accountEmail);
    }
  };

  return (
    <div className="animate-slide-up max-w-4xl mx-auto space-y-gutter">
      <div className="card">
        <div className="mb-6">
          <h2 className="font-headline text-headline-lg text-text-primary">About</h2>
          <p className="text-text-secondary mt-1">EOS Payslip Tool information and updates.</p>
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-between py-3 border-b border-border-light">
            <div>
              <p className="font-label text-label-md text-text-primary">Version</p>
              <p className="text-text-secondary text-body-sm">Current installed version</p>
            </div>
            <span className="px-3 py-1 bg-primary-container/10 text-primary-container rounded-full text-sm font-medium">
              v1.0.4
            </span>
          </div>

          <div className="flex items-center justify-between py-3 border-b border-border-light">
            <div>
              <p className="font-label text-label-md text-text-primary">Platform</p>
              <p className="text-text-secondary text-body-sm">Operating system</p>
            </div>
            <span className="text-text-primary font-label text-label-md">
              {navigator.platform}
            </span>
          </div>

          <div className="flex items-center justify-between py-3">
            <div>
              <p className="font-label text-label-md text-text-primary">Releases</p>
              <p className="text-text-secondary text-body-sm">Download the latest version</p>
            </div>
            <a
              href="https://github.com/moonstarph23/eos-payslip-tool/releases/latest"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline font-label text-label-md flex items-center gap-1"
            >
              <span className="material-symbols-outlined text-[16px]">open_in_new</span>
              GitHub
            </a>
          </div>
        </div>
      </div>

      {/* Email Accounts Management */}
      <div className="card">
        <div className="mb-6">
          <h2 className="font-headline text-headline-lg text-text-primary">Email Accounts</h2>
          <p className="text-text-secondary mt-1">
            Manage Gmail accounts and their aliases. Add your main email accounts, then add aliases for each.
          </p>
        </div>

        <div className="space-y-4">
          {/* Add new account */}
          <div className="flex items-start gap-2">
            <div className="flex-grow space-y-1">
              <div className="relative">
                <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-text-muted">account_circle</span>
                <input
                  type="email"
                  value={newAccountEmail}
                  onChange={(e) => {
                    setNewAccountEmail(e.target.value);
                    if (newAccountError) setNewAccountError('');
                  }}
                  onKeyDown={handleAccountKeyDown}
                  placeholder="e.g. example@gmail.com"
                  className={`input-field pl-10 ${newAccountError ? 'border-error focus:border-error focus:ring-error/20' : ''}`}
                />
              </div>
              {newAccountError && (
                <p className="text-body-sm text-error flex items-center gap-1">
                  <span className="material-symbols-outlined text-[16px]">error</span>
                  {newAccountError}
                </p>
              )}
            </div>
            <button
              type="button"
              onClick={handleAddAccount}
              disabled={loading}
              className="px-5 py-3 bg-primary-container text-white rounded-lg font-label text-label-md hover:scale-[1.02] active:translate-y-px transition-all shadow-md flex items-center gap-2 whitespace-nowrap disabled:opacity-70"
            >
              <span className="material-symbols-outlined text-[18px]">add</span>
              Add Account
            </button>
          </div>

          {/* Accounts list */}
          {loading ? (
            <div className="bg-surface-container-low rounded-lg p-4 text-center">
              <span className="material-symbols-outlined text-text-muted animate-spin text-2xl">sync</span>
              <p className="text-text-secondary text-body-sm mt-2">Loading accounts...</p>
            </div>
          ) : accounts.length === 0 ? (
            <div className="bg-surface-container-low rounded-lg p-4 text-center">
              <span className="material-symbols-outlined text-text-muted text-3xl mb-2">mail_outline</span>
              <p className="text-text-secondary text-body-sm">No email accounts configured yet.</p>
              <p className="text-text-muted text-body-xs mt-1">
                Add your Gmail accounts here, then add aliases from Gmail Settings → "Send mail as"
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {accounts.map((account) => (
                <div key={account.email} className="border border-border-light rounded-xl overflow-hidden">
                  {/* Account header */}
                  <div className="flex items-center justify-between p-4 bg-surface-container-low">
                    <div className="flex items-center gap-3">
                      <span className="material-symbols-outlined text-primary-container">account_circle</span>
                      <div>
                        <p className="font-label text-label-md text-text-primary">{account.email}</p>
                        <p className="text-text-secondary text-body-xs">{account.aliases.length} alias{account.aliases.length !== 1 ? 'es' : ''}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => setActiveAccount(activeAccount === account.email ? null : account.email)}
                        className="px-3 py-1.5 text-primary text-sm font-medium hover:bg-primary-container/10 rounded-lg transition-colors flex items-center gap-1"
                      >
                        <span className="material-symbols-outlined text-[16px]">{activeAccount === account.email ? 'expand_less' : 'expand_more'}</span>
                        {activeAccount === account.email ? 'Collapse' : 'Manage'}
                      </button>
                      <button
                        type="button"
                        onClick={() => handleRemoveAccount(account.email)}
                        className="p-1.5 text-text-muted hover:text-error hover:bg-error/10 rounded-lg transition-colors"
                        title="Remove account"
                      >
                        <span className="material-symbols-outlined text-[18px]">delete</span>
                      </button>
                    </div>
                  </div>

                  {/* Aliases section (expandable) */}
                  {activeAccount === account.email && (
                    <div className="p-4 border-t border-border-light space-y-3">
                      {/* Add alias */}
                      <div className="space-y-3">
                        <div className="grid grid-cols-2 gap-2">
                          <div className="relative">
                            <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-text-muted">alternate_email</span>
                            <input
                              type="email"
                              value={newAliasEmail}
                              onChange={(e) => {
                                setNewAliasEmail(e.target.value);
                                if (newAliasError) setNewAliasError('');
                              }}
                              onKeyDown={(e) => handleAliasKeyDown(e, account.email)}
                              placeholder="Alias email"
                              className={`input-field pl-10 text-sm ${newAliasError ? 'border-error focus:border-error focus:ring-error/20' : ''}`}
                            />
                          </div>
                          <div className="relative">
                            <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-text-muted">badge</span>
                            <input
                              type="text"
                              value={newAliasName}
                              onChange={(e) => setNewAliasName(e.target.value)}
                              onKeyDown={(e) => handleAliasKeyDown(e, account.email)}
                              placeholder="Display name (optional)"
                              className="input-field pl-10 text-sm"
                            />
                          </div>
                        </div>
                        {newAliasError && (
                          <p className="text-body-sm text-error flex items-center gap-1">
                            <span className="material-symbols-outlined text-[16px]">error</span>
                            {newAliasError}
                          </p>
                        )}
                        <button
                          type="button"
                          onClick={() => handleAddAlias(account.email)}
                          className="px-4 py-2.5 bg-primary-container text-white rounded-lg font-label text-label-sm hover:scale-[1.02] active:translate-y-px transition-all shadow-md flex items-center gap-1 whitespace-nowrap"
                        >
                          <span className="material-symbols-outlined text-[16px]">add</span>
                          Add Alias
                        </button>
                      </div>

                      {/* Alias list */}
                      {account.aliases.length === 0 ? (
                        <p className="text-text-muted text-body-sm py-2">No aliases added yet.</p>
                      ) : (
                        <div className="space-y-1">
                          {account.aliases.map((alias) => (
                            <div
                              key={alias.email}
                              className="flex items-center justify-between p-2 bg-white rounded-lg border border-border-light"
                            >
                              <div className="flex items-center gap-2">
                                <span className="material-symbols-outlined text-text-muted text-[18px]">alternate_email</span>
                                <div>
                                  {alias.display_name ? (
                                    <p className="text-text-primary text-body-sm font-medium">{alias.display_name}</p>
                                  ) : null}
                                  <p className={`text-body-sm ${alias.display_name ? 'text-text-secondary' : 'text-text-primary'}`}>{alias.email}</p>
                                </div>
                              </div>
                              <button
                                type="button"
                                onClick={() => handleRemoveAlias(account.email, alias.email)}
                                className="p-1 text-text-muted hover:text-error hover:bg-error/10 rounded transition-colors"
                                title="Remove alias"
                              >
                                <span className="material-symbols-outlined text-[16px]">delete</span>
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="card">
        <div className="mb-6">
          <h2 className="font-headline text-headline-lg text-text-primary">Support</h2>
          <p className="text-text-secondary mt-1">Get help with the application.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <a 
            href="mailto:payroll@eosglobalexpansion.com" 
            className="flex items-center gap-4 p-4 bg-surface-container-low rounded-lg hover:bg-surface-container transition-colors"
          >
            <div className="w-10 h-10 bg-primary-container/10 rounded-lg flex items-center justify-center">
              <span className="material-symbols-outlined text-primary-container">mail</span>
            </div>
            <div>
              <p className="font-label text-label-md text-text-primary">Email Support</p>
              <p className="text-text-secondary text-body-sm">payroll@eosglobalexpansion.com</p>
            </div>
          </a>

          <div className="flex items-center gap-4 p-4 bg-surface-container-low rounded-lg">
            <div className="w-10 h-10 bg-secondary-container/10 rounded-lg flex items-center justify-center">
              <span className="material-symbols-outlined text-secondary-container">help</span>
            </div>
            <div>
              <p className="font-label text-label-md text-text-primary">Documentation</p>
              <p className="text-text-secondary text-body-sm">View user guide and FAQ</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsTab;
