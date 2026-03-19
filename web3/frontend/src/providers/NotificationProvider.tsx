'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import toast from 'react-hot-toast';

interface Notification {
  id: string;
  type: 'signal' | 'staking' | 'governance' | 'nft' | 'general';
  title: string;
  message: string;
  timestamp: number;
  read: boolean;
  actionUrl?: string;
}

interface NotificationContextType {
  notifications: Notification[];
  unreadCount: number;
  addNotification: (notification: Omit<Notification, 'id' | 'timestamp' | 'read'>) => void;
  markAsRead: (id: string) => void;
  markAllAsRead: () => void;
  clearAll: () => void;
}

const NotificationContext = createContext<NotificationContextType | undefined>(undefined);

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [notifications, setNotifications] = useState<Notification[]>([]);

  // Load notifications from localStorage
  useEffect(() => {
    const stored = localStorage.getItem('fibtool_notifications');
    if (stored) {
      setNotifications(JSON.parse(stored));
    }
  }, []);

  // Save notifications to localStorage
  useEffect(() => {
    localStorage.setItem('fibtool_notifications', JSON.stringify(notifications));
  }, [notifications]);

  // Request notification permission
  useEffect(() => {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }
  }, []);

  const unreadCount = notifications.filter((n) => !n.read).length;

  const addNotification = (notification: Omit<Notification, 'id' | 'timestamp' | 'read'>) => {
    const newNotification: Notification = {
      ...notification,
      id: Date.now().toString(),
      timestamp: Date.now(),
      read: false,
    };

    setNotifications((prev) => [newNotification, ...prev]);

    // Show toast
    toast.success(notification.title);

    // Show browser notification
    if ('Notification' in window && Notification.permission === 'granted') {
      new Notification(notification.title, {
        body: notification.message,
        icon: '/icons/icon-192x192.png',
        badge: '/icons/icon-72x72.png',
        tag: newNotification.id,
      });
    }
  };

  const markAsRead = (id: string) => {
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read: true } : n))
    );
  };

  const markAllAsRead = () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  };

  const clearAll = () => {
    setNotifications([]);
  };

  return (
    <NotificationContext.Provider
      value={{
        notifications,
        unreadCount,
        addNotification,
        markAsRead,
        markAllAsRead,
        clearAll,
      }}
    >
      {children}
    </NotificationContext.Provider>
  );
}

export function useNotifications() {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error('useNotifications must be used within NotificationProvider');
  }
  return context;
}

// Hook to simulate real-time notifications
export function useNotificationSimulator() {
  const { addNotification } = useNotifications();

  useEffect(() => {
    // Simulate notifications every 30 seconds
    const interval = setInterval(() => {
      const notifications = [
        {
          type: 'signal' as const,
          title: 'New Signal Available',
          message: 'Fibonacci Retracement Master has posted a new EURUSD signal',
          actionUrl: '/marketplace/1',
        },
        {
          type: 'staking' as const,
          title: 'Rewards Ready to Claim',
          message: 'You have 42.5 FIBT rewards available to claim',
          actionUrl: '/staking',
        },
        {
          type: 'governance' as const,
          title: 'New Governance Proposal',
          message: 'Proposal #15: Reduce platform fees by 25%',
          actionUrl: '/governance',
        },
      ];

      // Randomly show a notification
      if (Math.random() > 0.7) {
        const randomNotif = notifications[Math.floor(Math.random() * notifications.length)];
        addNotification(randomNotif);
      }
    }, 30000);

    return () => clearInterval(interval);
  }, [addNotification]);
}
