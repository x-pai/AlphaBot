/** @type {import('next').NextConfig} */
const nextConfig = {
  /* config options here */
  output: 'standalone',

  experimental: {
    // 设置代理超时为300秒
    proxyTimeout: 300000,
  },
  
  async rewrites() {
    // 根据环境变量决定使用哪个目标URL
    // 注意：在某些环境中process.env.NODE_ENV可能为undefined
    const nodeEnv = process.env.NODE_ENV || 'development';
    const isProduction = nodeEnv === 'production';
    
    // 在开发环境中使用localhost，在生产环境中使用Docker服务名
    const apiDestination = isProduction 
      ? 'http://backend:8000/api/:path*'  // Docker环境
      : 'http://localhost:8000/api/:path*'; // 本地开发环境
    
    console.log(`Next.js rewrites: Environment=${nodeEnv}, API destination=${apiDestination}`);
    
    // 确保所有API路径都被重定向，包括嵌套路径
    return [
      {
        // 使用:path*捕获所有路径段，包括嵌套路径
        source: '/api/:path*',
        destination: apiDestination,
      },
    ];
  },
};

export default nextConfig; 