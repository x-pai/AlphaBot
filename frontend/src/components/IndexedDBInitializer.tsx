'use client';

import { useEffect } from 'react';
import { indexedDBCache } from '../lib/indexedDBCache';

/**
 * 初始化IndexedDB缓存的客户端组件
 * 这个组件不渲染任何UI，只在客户端初始化IndexedDB
 */
export default function IndexedDBInitializer() {
  useEffect(() => {
    // 初始化IndexedDB缓存
    indexedDBCache.init().catch(err => {
      console.error('Failed to initialize IndexedDB cache:', err);
    });
  }, []);

  // 不渲染任何内容
  return null;
} 