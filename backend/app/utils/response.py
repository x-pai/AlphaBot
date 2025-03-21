from typing import Any, Dict, Optional, TypeVar, Generic, Union

T = TypeVar('T')

def api_response(
    success: bool = True, 
    data: Optional[Any] = None, 
    error: Optional[str] = None
) -> Dict[str, Any]:
    """
    创建统一的API响应格式
    
    Args:
        success: 请求是否成功
        data: 响应数据
        error: 错误信息
        
    Returns:
        统一格式的响应字典
    """
    response = {"success": success}
    
    if data is not None:
        response["data"] = data
        
    if error is not None:
        response["error"] = error
        
    return response 