'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useNotifications } from '@/providers/NotificationProvider';
import { FiBell, FiX, FiCheck } from 'react-icons/fi';
import { formatRelativeTime } from '@/utils/helpers';

const NOTIFICATION_ICONS = {
  signal: '📊',
  staking: '💰',
  governance: '🗳️',
  nft: '🎨',
  general: 'ℹ️',
};

export function NotificationBell() {
  const [isOpen, setIsOpen] = useState(false);
  const { notifications, unreadCount, markAsRead, markAllAsRead, clearAll } = useNotifications();

  return (
    <div className="relative">
      {/* Bell Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 text-gray-400 hover:text-white transition"
      >
        <FiBell className="text-xl" />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 bg-error text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
          />

          {/* Dropdown Panel */}
          <div className="absolute right-0 mt-2 w-96 glass rounded-xl shadow-xl z-50 max-h-[600px] overflow-hidden flex flex-col">
            {/* Header */}
            <div className="p-4 border-b border-gray-700 flex justify-between items-center">
              <h3 className="text-lg font-bold text-white">Notifications</h3>
              <div className="flex space-x-2">
                {notifications.length > 0 && (
                  <>
                    <button
                      onClick={markAllAsRead}
                      className="text-sm text-primary-500 hover:text-primary-400 transition"
                      title="Mark all as read"
                    >
                      <FiCheck />
                    </button>
                    <button
                      onClick={clearAll}
                      className="text-sm text-gray-400 hover:text-white transition"
                      title="Clear all"
                    >
                      <FiX />
                    </button>
                  </>
                )}
              </div>
            </div>

            {/* Notifications List */}
            <div className="overflow-y-auto flex-1">
              {notifications.length === 0 ? (
                <div className="p-8 text-center text-gray-400">
                  <FiBell className="text-4xl mx-auto mb-3 opacity-50" />
                  <p>No notifications yet</p>
                </div>
              ) : (
                <div className="divide-y divide-gray-700">
                  {notifications.map((notification) => (
                    <div
                      key={notification.id}
                      className={`p-4 hover:bg-gray-800 transition ${
                        !notification.read ? 'bg-primary-600/5' : ''
                      }`}
                    >
                      {notification.actionUrl ? (
                        <Link
                          href={notification.actionUrl}
                          onClick={() => {
                            markAsRead(notification.id);
                            setIsOpen(false);
                          }}
                        >
                          <NotificationItem notification={notification} />
                        </Link>
                      ) : (
                        <div onClick={() => markAsRead(notification.id)}>
                          <NotificationItem notification={notification} />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function NotificationItem({ notification }: { notification: any }) {
  return (
    <div className="flex items-start space-x-3">
      <span className="text-2xl">{NOTIFICATION_ICONS[notification.type as keyof typeof NOTIFICATION_ICONS]}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between">
          <p className="text-white font-semibold text-sm">{notification.title}</p>
          {!notification.read && (
            <div className="w-2 h-2 bg-primary-600 rounded-full mt-1 ml-2" />
          )}
        </div>
        <p className="text-gray-400 text-sm mt-1">{notification.message}</p>
        <p className="text-gray-500 text-xs mt-2">
          {formatRelativeTime(notification.timestamp / 1000)}
        </p>
      </div>
    </div>
  );
}
