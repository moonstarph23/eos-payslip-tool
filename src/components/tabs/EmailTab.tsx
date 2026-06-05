import React, { useState, useCallback, useEffect, useRef } from 'react';
import { LogEntry } from '../LogConsole';
import { openFileDialog, openFolder, spawnSidecar } from '../../hooks/useTauri';
import { listen } from '@tauri-apps/api/event';
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

interface EmailTabProps {
  onLog: (entry: LogEntry) => void;
}

const DEFAULT_SUBJECT = 'Payslip: {filename}';

const DEFAULT_BODY = `Dear {EMPLOYEE'S NAME},

Payslip attached for the period: {Pay. Period}.
Password is your birthday in MMDDYYYY format.
For January 31, 1990, password is 01311990

This is an automated message.

EOS PAYROLL TEAM`;

const isValidEmail = (email: string): boolean => {
  const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return regex.test(email.trim());
};

const EmailTab: React.FC<EmailTabProps> = ({ onLog }) => {
  const [manifestFile, setManifestFile] = useState('');
  const [mainEmail, setMainEmail] = useState('');
  const [subject, setSubject] = useState(DEFAULT_SUBJECT);
  const [body, setBody] = useState(DEFAULT_BODY);
  const [appPassword, setAppPassword] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [mainEmailError, setMainEmailError] = useState('');
  
  // Saved accounts from settings
  const [savedAccounts, setSavedAccounts] = useState<EmailAccount[]>([]);
  const [accountsLoading, setAccountsLoading] = useState(true);

  // Send email modal state
  const [showSendModal, setShowSendModal] = useState(false);
  const [sendAlias, setSendAlias] = useState('');

  // Test email modal state
  const [showTestModal, setShowTestModal] = useState(false);
  const [testRecipient, setTestRecipient] = useState('');
  const [testRecipientError, setTestRecipientError] = useState('');
  const [testAlias, setTestAlias] = useState('');

  // Listen for sidecar real-time logs (stdout/stderr)
  const logCounterRef = useRef(0);
  const makeLogId = useCallback(() => {
    return `${Date.now()}-${++logCounterRef.current}`;
  }, []);

  useEffect(() => {
    let unlistenOut: (() => void) | undefined;
    let unlistenErr: (() => void) | undefined;
    let mounted = true;

    const setup = async () => {
      unlistenOut = await listen<string>('sidecar-stdout', (event) => {
        if (!mounted) return;
        try {
          const parsed = JSON.parse(event.payload);
          if (parsed.type === 'log') {
            onLog({
              id: makeLogId(),
              timestamp: parsed.timestamp || new Date().toLocaleTimeString('en-GB', { hour12: false }),
              level: parsed.level || 'INFO',
              message: parsed.message,
            });
          }
        } catch {
          onLog({
            id: makeLogId(),
            timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false }),
            level: 'INFO',
            message: event.payload,
          });
        }
      });

      unlistenErr = await listen<string>('sidecar-stderr', (event) => {
        if (!mounted) return;
        onLog({
          id: makeLogId(),
          timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false }),
          level: 'INFO',
          message: `[SMTP] ${event.payload}`,
        });
      });
    };

    setup();

    return () => {
      mounted = false;
      unlistenOut?.();
      unlistenErr?.();
    };
  }, [onLog, makeLogId]);

  // Load saved accounts from settings
  useEffect(() => {
    const loadAccounts = async () => {
      try {
        const result = await invoke<EmailAccount[]>('get_email_accounts');
        if (Array.isArray(result)) {
          setSavedAccounts(result.filter((a) => a.email && a.email.includes('@')));
        }
      } catch (err) {
        console.error('Failed to load email accounts:', err);
      } finally {
        setAccountsLoading(false);
      }
    };
    loadAccounts();
  }, []);

  // Auto-set alias when main email changes
  useEffect(() => {
    const account = savedAccounts.find((a) => a.email === mainEmail);
    if (account && account.aliases.length > 0) {
      setSendAlias(account.aliases[0].email);
      setTestAlias(account.aliases[0].email);
    } else {
      setSendAlias(mainEmail);
      setTestAlias(mainEmail);
    }
  }, [mainEmail, savedAccounts]);

  const handleBrowse = async () => {
    const result = await openFileDialog({
      title: 'Select Payslips Manifest',
      filters: [
        { name: 'Excel Files', extensions: ['xlsx', 'xls'] },
        { name: 'All Files', extensions: ['*'] },
      ],
    });
    if (result && typeof result === 'string') {
      setManifestFile(result);
      onLog({
        id: Date.now().toString(),
        timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false }),
        level: 'INFO',
        message: `Selected manifest: ${result}`,
      });
    }
  };

  const validateForm = (): boolean => {
    let valid = true;
    if (!isValidEmail(mainEmail)) {
      setMainEmailError('Please enter a valid main email address');
      valid = false;
    } else {
      setMainEmailError('');
    }
    if (!manifestFile || !appPassword) {
      onLog({
        id: Date.now().toString(),
        timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false }),
        level: 'WARNING',
        message: 'Please fill in all required fields before sending emails.',
      });
      valid = false;
    }
    return valid;
  };

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;
    // Don't reset sendAlias here — keep the user's selected alias (or default from useEffect)
    setShowSendModal(true);
  };

  const handleConfirmSend = async () => {
    setShowSendModal(false);
    setIsSending(true);
    onLog({
      id: Date.now().toString(),
      timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false }),
      level: 'INFO',
      message: `Starting email distribution using alias: ${sendAlias}...`,
    });

    try {
      const account = savedAccounts.find((a) => a.email === mainEmail);
      const aliasObj = account?.aliases.find((al) => al.email === sendAlias);
      const config = {
        email: mainEmail,
        alias: sendAlias,
        alias_name: aliasObj?.display_name || '',
        subject: subject || DEFAULT_SUBJECT,
        body: body || DEFAULT_BODY,
        app_password: appPassword,
      };

      const result = (await spawnSidecar('send_emails', [
        '--manifest', manifestFile,
        '--config', JSON.stringify(config),
      ])) as Record<string, unknown> | undefined;

      if (result && result.success === false) {
        throw new Error((result.error as string) || 'Unknown sidecar error');
      }

      onLog({
        id: Date.now().toString(),
        timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false }),
        level: 'SUCCESS',
        message: `Email distribution complete.`,
      });

      // Open the folder containing the manifest (output saved there)
      const manifestFolder = manifestFile.substring(0, manifestFile.lastIndexOf('\\'));
      if (manifestFolder) {
        setTimeout(() => openFolder(manifestFolder), 800);
      }
    } catch (err) {
      onLog({
        id: Date.now().toString(),
        timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false }),
        level: 'ERROR',
        message: `Email sending failed: ${err}`,
      });
    } finally {
      setIsSending(false);
    }
  };

  const openTestModal = () => {
    if (!isValidEmail(mainEmail)) {
      setMainEmailError('Please enter a valid main email address');
      return;
    }
    setMainEmailError('');

    if (!appPassword) {
      onLog({
        id: Date.now().toString(),
        timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false }),
        level: 'WARNING',
        message: 'Please enter the app password before testing.',
      });
      return;
    }

    setTestRecipient('');
    setTestRecipientError('');
    setTestAlias(getSelectedAlias());
    setShowTestModal(true);
  };

  const closeTestModal = () => {
    setShowTestModal(false);
    setTestRecipient('');
    setTestRecipientError('');
    setTestAlias('');
  };

  const getSelectedAlias = () => {
    const account = savedAccounts.find((a) => a.email === mainEmail);
    if (account && account.aliases.length > 0) {
      return account.aliases[0].email;
    }
    return mainEmail;
  };

  const getAliasesForAccount = (): Alias[] => {
    const account = savedAccounts.find((a) => a.email === mainEmail);
    if (account && account.aliases.length > 0) {
      return account.aliases;
    }
    return [{ email: mainEmail, display_name: '' }];
  };

  const handleConfirmTest = async () => {
    if (!isValidEmail(testRecipient)) {
      setTestRecipientError('Please enter a valid email address');
      return;
    }
    setTestRecipientError('');
    setShowTestModal(false);

    setIsTesting(true);
    onLog({
      id: Date.now().toString(),
      timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false }),
      level: 'INFO',
      message: `Sending test email to ${testRecipient}...`,
    });

    try {
      const testSubject = (subject || DEFAULT_SUBJECT)
        .replace(/{filename}/g, 'Test')
        .replace(/{EMPLOYEE'S NAME}/g, 'Test')
        .replace(/{Pay\. Period}/g, 'Test');

      const testBody = (body || DEFAULT_BODY)
        .replace(/{EMPLOYEE'S NAME}/g, 'Test')
        .replace(/{Pay\. Period}/g, 'Test')
        .replace(/{filename}/g, 'Test');

      const account = savedAccounts.find((a) => a.email === mainEmail);
      const aliasObj = account?.aliases.find((al) => al.email === testAlias);
      const config = {
        email: mainEmail,
        alias: testAlias || mainEmail,
        alias_name: aliasObj?.display_name || '',
        recipient: testRecipient,
        subject: testSubject,
        body: testBody,
        app_password: appPassword,
      };

      const result = (await spawnSidecar('test_email', [
        '--config', JSON.stringify(config),
      ])) as Record<string, unknown> | undefined;

      if (result && result.success === false) {
        throw new Error((result.error as string) || 'Unknown sidecar error');
      }

      onLog({
        id: Date.now().toString(),
        timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false }),
        level: 'SUCCESS',
        message: `Test email sent successfully to ${testRecipient}!`,
      });
    } catch (err) {
      onLog({
        id: Date.now().toString(),
        timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false }),
        level: 'ERROR',
        message: `Test email failed: ${err}`,
      });
    } finally {
      setIsTesting(false);
    }
  };

  const handleMainEmailChange = (value: string) => {
    setMainEmail(value);
    if (mainEmailError) setMainEmailError('');
  };

  return (
    <div className="animate-slide-up">
      <div className="max-w-4xl mx-auto">
        {/* Breadcrumb */}
        <nav className="flex items-center gap-2 mb-6 text-body-sm text-text-secondary">
          <span>Payroll Processing</span>
          <span className="material-symbols-outlined text-[16px]">chevron_right</span>
          <span className="text-primary font-medium">Email Distribution</span>
        </nav>

        {/* Main Card */}
        <div className="card">
          <div className="flex items-center justify-between mb-8 border-b border-border-light pb-6">
            <div>
              <h2 className="font-headline text-headline-lg text-primary">Email Distribution</h2>
              <p className="text-text-secondary font-body text-body-md mt-1">
                Configure and initiate the mass dispatch of monthly payslips to employees.
              </p>
            </div>
          </div>

          <form onSubmit={handleSend} className="space-y-6">
            {/* Payslips Manifest */}
            <div className="space-y-2">
              <label className="block font-label text-label-md text-text-primary">Payslips Manifest</label>
              <div className="flex items-center gap-2">
                <div className="relative flex-grow">
                  <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-text-muted">description</span>
                  <input 
                    className="input-readonly pl-10"
                    readOnly 
                    value={manifestFile}
                    placeholder="Select payslips manifest file"
                    type="text"
                  />
                </div>
                <button 
                  type="button"
                  onClick={handleBrowse}
                  className="btn-secondary"
                >
                  Browse
                </button>
              </div>
            </div>

            {/* Main Email (Account Dropdown) */}
            <div className="space-y-2">
              <label className="block font-label text-label-md text-text-primary">Main Account (SMTP Login)</label>
              {accountsLoading ? (
                <div className="input-field pl-10 flex items-center gap-2 text-text-muted">
                  <span className="material-symbols-outlined animate-spin text-[16px]">sync</span>
                  Loading accounts...
                </div>
              ) : savedAccounts.length > 0 ? (
                <div className="relative">
                  <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-text-muted">account_circle</span>
                  <select
                    value={mainEmail}
                    onChange={(e) => handleMainEmailChange(e.target.value)}
                    className={`input-field pl-10 appearance-none pr-10 ${mainEmailError ? 'border-error focus:border-error focus:ring-error/20' : ''}`}
                  >
                    <option value="">Select an account...</option>
                    {savedAccounts.map((account) => (
                      <option key={account.email} value={account.email}>
                        {account.email} ({account.aliases.length} alias{account.aliases.length !== 1 ? 'es' : ''})
                      </option>
                    ))}
                  </select>
                  <span className="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none">expand_more</span>
                </div>
              ) : null}
              
              {mainEmailError && (
                <p className="text-body-sm text-error flex items-center gap-1">
                  <span className="material-symbols-outlined text-[16px]">error</span>
                  {mainEmailError}
                </p>
              )}
              <p className="text-body-sm text-text-secondary">
                The Gmail account used to log in. Add accounts in Settings → Email Accounts.
              </p>
            </div>

            {/* Subject Input */}
            <div className="space-y-2">
              <label className="block font-label text-label-md text-text-primary">Subject</label>
              <input 
                className="input-field"
                placeholder="e.g. Payslip: {filename}"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                type="text"
              />
              <p className="text-body-sm text-text-secondary">
                Available variables: {'{filename}'}, {'{EMPLOYEE\'S NAME}'}, {'{Pay. Period}'}
              </p>
            </div>

            {/* Email Body Editor */}
            <div className="space-y-2">
              <label className="block font-label text-label-md text-text-primary">Email Body</label>
              <div className="border border-border-light rounded-lg overflow-hidden focus-within:ring-2 focus-within:ring-primary-container/20 focus-within:border-primary-container transition-all">
                <div className="bg-surface-container-low px-3 py-2 border-b border-border-light flex gap-1">
                  <button type="button" className="p-1.5 hover:bg-white rounded transition-colors text-text-secondary hover:text-primary">
                    <span className="material-symbols-outlined text-[20px]">format_bold</span>
                  </button>
                  <button type="button" className="p-1.5 hover:bg-white rounded transition-colors text-text-secondary hover:text-primary">
                    <span className="material-symbols-outlined text-[20px]">format_italic</span>
                  </button>
                  <button type="button" className="p-1.5 hover:bg-white rounded transition-colors text-text-secondary hover:text-primary">
                    <span className="material-symbols-outlined text-[20px]">link</span>
                  </button>
                  <div className="w-px h-5 bg-border-light mx-1 self-center"></div>
                  <button type="button" className="p-1.5 hover:bg-white rounded transition-colors text-text-secondary hover:text-primary">
                    <span className="material-symbols-outlined text-[20px]">format_list_bulleted</span>
                  </button>
                </div>
                <textarea 
                  className="w-full p-4 text-body-md h-[150px] outline-none resize-none bg-white"
                  placeholder="Dear {EMPLOYEE'S NAME}, please find your payslip for the month of..."
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                />
              </div>
              <p className="text-body-sm text-text-secondary">
                Available variables: {'{EMPLOYEE\'S NAME}'}, {'{Pay. Period}'}, {'{filename}'}
              </p>
            </div>

            {/* App Password */}
            <div className="space-y-2">
              <label className="block font-label text-label-md text-text-primary">App Password</label>
              <input 
                className="input-field"
                type="text"
                value={appPassword}
                onChange={(e) => setAppPassword(e.target.value)}
                placeholder="Enter your SMTP app password"
              />
              <p className="text-body-sm text-text-secondary">Use your dedicated SMTP app password for authentication.</p>
            </div>

            {/* Action Buttons */}
            <div className="pt-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <button 
                  type="button"
                  onClick={openTestModal}
                  disabled={isTesting || isSending}
                  className={`px-6 py-3.5 bg-surface-container-high text-primary border border-primary-container rounded-lg font-headline text-headline-sm hover:bg-primary-container/10 active:translate-y-px active:shadow-inner transition-all shadow-sm flex items-center gap-2 ${isTesting || isSending ? 'opacity-70 cursor-not-allowed' : ''}`}
                >
                  <span className="material-symbols-outlined">outgoing_mail</span>
                  {isTesting ? 'Testing...' : 'Test Email'}
                </button>
                <button 
                  type="submit"
                  disabled={isSending || isTesting}
                  className={`px-10 py-3.5 bg-primary-container text-white rounded-lg font-headline text-headline-sm hover:scale-[1.02] active:translate-y-px active:shadow-inner transition-all shadow-md flex items-center gap-2 ${isSending || isTesting ? 'opacity-70 cursor-not-allowed' : ''}`}
                >
                  <span className="material-symbols-outlined">send</span>
                  {isSending ? 'Sending...' : 'Send Emails'}
                </button>
              </div>
            </div>
          </form>
        </div>
      </div>

      {/* Send Email Alias Selection Modal */}
      {showSendModal && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 p-6 animate-fade-in">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-primary-container/10 rounded-full flex items-center justify-center">
                <span className="material-symbols-outlined text-primary-container">send</span>
              </div>
              <div>
                <h3 className="font-headline text-headline-md text-primary">Send Emails</h3>
                <p className="text-body-sm text-text-secondary">Choose the alias to send from.</p>
              </div>
            </div>

            <div className="space-y-4 mb-6">
              <div className="space-y-2">
                <label className="block font-label text-label-md text-text-primary">Send As Alias</label>
                {getAliasesForAccount().length > 0 ? (
                  <div className="relative">
                    <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-text-muted">alternate_email</span>
                    <select
                      value={sendAlias}
                      onChange={(e) => setSendAlias(e.target.value)}
                      className="input-field pl-10 appearance-none pr-10"
                    >
                      {getAliasesForAccount().map((alias) => (
                        <option key={alias.email} value={alias.email}>
                          {alias.display_name ? `${alias.display_name} <${alias.email}>` : alias.email}
                        </option>
                      ))}
                    </select>
                    <span className="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none">expand_more</span>
                  </div>
                ) : (
                  <div className="relative">
                    <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-text-muted">alternate_email</span>
                    <input
                      type="email"
                      value={sendAlias}
                      onChange={(e) => setSendAlias(e.target.value)}
                      placeholder="e.g. delivery.JP@rivermate.com"
                      className="input-field pl-10"
                    />
                  </div>
                )}
                <p className="text-body-sm text-text-secondary">
                  {getAliasesForAccount().length > 0 
                    ? 'Select an alias for this account.' 
                    : 'Type the alias you want to send from. Defaults to your main email.'}
                </p>
              </div>

              <div className="bg-surface-container-low rounded-lg p-3 text-body-sm text-text-secondary">
                <p><strong>Manifest:</strong> {manifestFile ? manifestFile.split('\\').pop() : 'None selected'}</p>
                <p><strong>Login Account:</strong> {mainEmail}</p>
                <p><strong>Send As:</strong> {sendAlias || mainEmail}</p>
                <p><strong>Recipients:</strong> From manifest file</p>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={() => setShowSendModal(false)}
                className="px-5 py-2.5 rounded-lg font-label text-label-md text-text-secondary hover:bg-surface-container-low transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmSend}
                disabled={isSending}
                className={`px-6 py-2.5 bg-primary-container text-white rounded-lg font-label text-label-md hover:scale-[1.02] active:translate-y-px transition-all shadow-md flex items-center gap-2 ${isSending ? 'opacity-70 cursor-not-allowed' : ''}`}
              >
                <span className="material-symbols-outlined text-[18px]">send</span>
                {isSending ? 'Sending...' : 'Confirm Send'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Test Email Modal */}
      {showTestModal && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 p-6 animate-fade-in">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-primary-container/10 rounded-full flex items-center justify-center">
                <span className="material-symbols-outlined text-primary-container">outgoing_mail</span>
              </div>
              <div>
                <h3 className="font-headline text-headline-md text-primary">Send Test Email</h3>
                <p className="text-body-sm text-text-secondary">Confirm the recipient for your test email.</p>
              </div>
            </div>

            <div className="space-y-4 mb-6">
              <div className="space-y-2">
                <label className="block font-label text-label-md text-text-primary">Test Recipient</label>
                <div className="relative">
                  <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-text-muted">person</span>
                  <input
                    type="email"
                    value={testRecipient}
                    onChange={(e) => {
                      setTestRecipient(e.target.value);
                      if (testRecipientError) setTestRecipientError('');
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleConfirmTest();
                    }}
                    placeholder="e.g. yourname@gmail.com"
                    className={`input-field pl-10 ${testRecipientError ? 'border-error focus:border-error focus:ring-error/20' : ''}`}
                    autoFocus
                  />
                </div>
                {testRecipientError && (
                  <p className="text-body-sm text-error flex items-center gap-1">
                    <span className="material-symbols-outlined text-[16px]">error</span>
                    {testRecipientError}
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <label className="block font-label text-label-md text-text-primary">Send As Alias</label>
                {getAliasesForAccount().length > 0 ? (
                  <div className="relative">
                    <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-text-muted">alternate_email</span>
                    <select
                      value={testAlias}
                      onChange={(e) => setTestAlias(e.target.value)}
                      className="input-field pl-10 appearance-none pr-10"
                    >
                      {getAliasesForAccount().map((alias) => (
                        <option key={alias.email} value={alias.email}>
                          {alias.display_name ? `${alias.display_name} <${alias.email}>` : alias.email}
                        </option>
                      ))}
                    </select>
                    <span className="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none">expand_more</span>
                  </div>
                ) : (
                  <div className="relative">
                    <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-text-muted">alternate_email</span>
                    <input
                      type="email"
                      value={testAlias}
                      onChange={(e) => setTestAlias(e.target.value)}
                      placeholder="e.g. delivery.JP@rivermate.com"
                      className="input-field pl-10"
                    />
                  </div>
                )}
                <p className="text-body-sm text-text-secondary">
                  {getAliasesForAccount().length > 0 
                    ? 'Select an alias for this account.' 
                    : 'Type the alias you want to send from. Defaults to your main email.'}
                </p>
              </div>

              <div className="bg-surface-container-low rounded-lg p-3 text-body-sm text-text-secondary">
                <p><strong>Login:</strong> {mainEmail}</p>
                <p><strong>Send As:</strong> {testAlias || mainEmail}</p>
                <p><strong>Subject:</strong> {(subject || DEFAULT_SUBJECT).replace(/{filename}/g, 'Test').replace(/{EMPLOYEE'S NAME}/g, 'Test').replace(/{Pay\. Period}/g, 'Test')}</p>
                <p className="mt-1 text-xs">Template variables will be replaced with "Test"</p>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={closeTestModal}
                className="px-5 py-2.5 rounded-lg font-label text-label-md text-text-secondary hover:bg-surface-container-low transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmTest}
                disabled={isTesting}
                className={`px-6 py-2.5 bg-primary-container text-white rounded-lg font-label text-label-md hover:scale-[1.02] active:translate-y-px transition-all shadow-md flex items-center gap-2 ${isTesting ? 'opacity-70 cursor-not-allowed' : ''}`}
              >
                <span className="material-symbols-outlined text-[18px]">send</span>
                {isTesting ? 'Sending...' : 'Send Test'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default EmailTab;
