'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { checkHealth } from '@/lib/api';

export default function Navigation() {
  const pathname = usePathname();
  const [isConnected, setIsConnected] = useState<boolean | null>(null);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  useEffect(() => {
    const checkConnection = async () => {
      try {
        await checkHealth();
        setIsConnected(true);
      } catch {
        setIsConnected(false);
      }
      setLastChecked(new Date());
    };

    checkConnection();
    const interval = setInterval(checkConnection, 5000);
    return () => clearInterval(interval);
  }, []);

  const navItems = [
    { href: '/', label: 'Dashboard' },
    { href: '/database', label: 'Database Explorer' },
  ];

  return (
    <nav className="bg-white border-b border-gray-200 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex items-center">
            <Link href="/" className="flex items-center">
              <span className="text-xl font-semibold text-gray-900">X-Ray</span>
              <span className="ml-2 text-xs text-gray-500">Decision Forensics</span>
            </Link>
            <div className="ml-10 flex items-center space-x-4">
              {navItems.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                    pathname === item.href
                      ? 'bg-blue-100 text-blue-700'
                      : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                  }`}
                >
                  {item.label}
                </Link>
              ))}
            </div>
          </div>
          <div className="flex items-center">
            <div className="flex items-center space-x-2">
              <div
                className={`w-2 h-2 rounded-full ${
                  isConnected === null
                    ? 'bg-gray-400'
                    : isConnected
                    ? 'bg-green-500'
                    : 'bg-red-500'
                }`}
              />
              <span className="text-sm text-gray-600">
                {isConnected === null
                  ? 'Checking...'
                  : isConnected
                  ? 'Connected'
                  : 'Disconnected'}
              </span>
              {lastChecked && (
                <span className="text-xs text-gray-400">
                  (checked {lastChecked.toLocaleTimeString()})
                </span>
              )}
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
}
