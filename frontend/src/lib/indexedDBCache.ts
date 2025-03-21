import { openDB, IDBPDatabase, StoreNames, IDBPObjectStore } from 'idb';

// 定义缓存项接口
interface CacheItem<T> {
  value: T;
  expireTime: number;
  lastAccessed: number;
}

// 定义缓存统计信息接口
export interface CacheStats {
  totalItems: number;
  activeItems: number;
  expiredItems: number;
  cacheKeys: string[];
}

class IndexedDBCacheService {
  private static instance: IndexedDBCacheService;
  private db: IDBPDatabase | null = null;
  private readonly dbName = 'stock-assistant-cache';
  private readonly storeName = 'cache-store';
  private _defaultTTL = 3600 * 1000; // 默认缓存时间为1小时（毫秒）
  private isInitialized = false;

  private constructor() {}

  public static getInstance(): IndexedDBCacheService {
    if (!IndexedDBCacheService.instance) {
      IndexedDBCacheService.instance = new IndexedDBCacheService();
    }
    return IndexedDBCacheService.instance;
  }

  /**
   * 初始化IndexedDB数据库
   */
  public async init(): Promise<void> {
    if (this.isInitialized) return;
    
    try {
      this.db = await openDB(this.dbName, 1, {
        upgrade(db: IDBPDatabase) {
          // 如果存储对象不存在，则创建
          if (!db.objectStoreNames.contains('cache-store')) {
            db.createObjectStore('cache-store');
          }
        },
      });
      this.isInitialized = true;
      console.log('IndexedDB cache initialized');
    } catch (error) {
      console.error('Failed to initialize IndexedDB cache:', error);
      throw error;
    }
  }

  /**
   * 获取缓存数据
   */
  public async get<T>(key: string): Promise<T | null> {
    await this.ensureInitialized();
    
    try {
      const cacheItem = await this.db!.get(this.storeName, key) as CacheItem<T> | undefined;
      
      if (!cacheItem) {
        return null;
      }
      
      const currentTime = Date.now();
      
      // 检查缓存是否过期
      if (currentTime > cacheItem.expireTime) {
        await this.delete(key);
        return null;
      }
      
      // 更新最后访问时间
      cacheItem.lastAccessed = currentTime;
      await this.db!.put(this.storeName, cacheItem, key);
      
      return cacheItem.value;
    } catch (error) {
      console.error(`Error getting cache for key ${key}:`, error);
      return null;
    }
  }

  /**
   * 设置缓存数据
   */
  public async set<T>(key: string, value: T, ttl?: number): Promise<void> {
    await this.ensureInitialized();
    
    const ttlMs = (ttl || this._defaultTTL);
    const expireTime = Date.now() + ttlMs;
    
    const cacheItem: CacheItem<T> = {
      value,
      expireTime,
      lastAccessed: Date.now()
    };
    
    try {
      await this.db!.put(this.storeName, cacheItem, key);
    } catch (error) {
      console.error(`Error setting cache for key ${key}:`, error);
      throw error;
    }
  }

  /**
   * 删除缓存数据
   */
  public async delete(key: string): Promise<boolean> {
    await this.ensureInitialized();
    
    try {
      await this.db!.delete(this.storeName, key);
      return true;
    } catch (error) {
      console.error(`Error deleting cache for key ${key}:`, error);
      return false;
    }
  }

  /**
   * 清空缓存
   */
  public async clear(): Promise<void> {
    await this.ensureInitialized();
    
    try {
      await this.db!.clear(this.storeName);
    } catch (error) {
      console.error('Error clearing cache:', error);
      throw error;
    }
  }

  /**
   * 清除匹配模式的缓存
   */
  public async clearPattern(pattern: string): Promise<number> {
    await this.ensureInitialized();
    
    try {
      const allKeys = await this.db!.getAllKeys(this.storeName);
      const keysToDelete = allKeys.filter(key => 
        typeof key === 'string' && key.includes(pattern)
      );
      
      for (const key of keysToDelete) {
        await this.db!.delete(this.storeName, key);
      }
      
      return keysToDelete.length;
    } catch (error) {
      console.error(`Error clearing cache with pattern ${pattern}:`, error);
      throw error;
    }
  }

  /**
   * 获取缓存统计信息
   */
  public async getStats(): Promise<CacheStats> {
    await this.ensureInitialized();
    
    try {
      const allKeys = await this.db!.getAllKeys(this.storeName);
      const allItems = await Promise.all(
        allKeys.map(async (key: IDBValidKey) => {
          const item = await this.db!.get(this.storeName, key);
          return { key, item };
        })
      );
      
      const currentTime = Date.now();
      const expiredItems = allItems.filter(({ item }: { item: any }) => 
        item && currentTime > item.expireTime
      );
      
      return {
        totalItems: allItems.length,
        activeItems: allItems.length - expiredItems.length,
        expiredItems: expiredItems.length,
        cacheKeys: allItems.map(({ key }: { key: IDBValidKey }) => key.toString())
      };
    } catch (error) {
      console.error('Error getting cache stats:', error);
      throw error;
    }
  }

  /**
   * 清理过期缓存
   */
  public async cleanup(): Promise<number> {
    await this.ensureInitialized();
    
    try {
      const allKeys = await this.db!.getAllKeys(this.storeName);
      const currentTime = Date.now();
      let deletedCount = 0;
      
      for (const key of allKeys) {
        const item = await this.db!.get(this.storeName, key);
        if (item && currentTime > item.expireTime) {
          await this.db!.delete(this.storeName, key);
          deletedCount++;
        }
      }
      
      return deletedCount;
    } catch (error) {
      console.error('Error cleaning up cache:', error);
      throw error;
    }
  }

  /**
   * 设置默认缓存时间
   */
  public setDefaultTTL(ttl: number): void {
    this._defaultTTL = ttl * 1000; // 转换为毫秒
  }

  /**
   * 确保数据库已初始化
   */
  private async ensureInitialized(): Promise<void> {
    if (!this.isInitialized) {
      await this.init();
    }
  }
}

// 导出单例实例
export const indexedDBCache = IndexedDBCacheService.getInstance();

// 缓存装饰器
export function cached<T>(ttl?: number) {
  return function(
    target: any,
    propertyKey: string,
    descriptor: PropertyDescriptor
  ) {
    const originalMethod = descriptor.value;
    
    descriptor.value = async function(...args: any[]) {
      const cache = IndexedDBCacheService.getInstance();
      const cacheKey = `${propertyKey}:${JSON.stringify(args)}`;
      
      // 尝试从缓存获取
      const cachedResult = await cache.get<T>(cacheKey);
      if (cachedResult !== null) {
        return cachedResult;
      }
      
      // 执行原方法
      const result = await originalMethod.apply(this, args);
      
      // 缓存结果
      if (result !== null && result !== undefined) {
        await cache.set<T>(cacheKey, result, ttl);
      }
      
      return result;
    };
    
    return descriptor;
  };
} 