from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt

# Minimal OpenAPI 3.0 spec describing the project's APIs
# Note: This is a hand-crafted spec based on current urlpatterns and view behaviors
OPENAPI_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "Dragon Optimize API",
        "version": "1.0.0",
        "description": "Dragon Optimize 系统优化平台的HTTP接口文档（基于Django函数视图，非DRF）。"
    },
    "paths": {
        "/api/{name}/{tp}/{number_range}/oneModel": {
            "post": {
                "summary": "通用模型CRUD",
                "parameters": [
                    {"name": "name", "in": "path", "required": True, "schema": {"type": "string"},
                     "description": "模型名称: JianKongFuWuQi | JianKongShuJuKu | FuWuXinXi"},
                    {"name": "tp", "in": "path", "required": True, "schema": {"type": "string"},
                     "description": "操作: create | select | update | del"},
                    {"name": "number_range", "in": "path", "required": True, "schema": {"type": "string"},
                     "description": "分页范围, 如 1-50"}
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"type": "object"}
                        }
                    }
                },
                "responses": {
                    "200": {"description": "成功"},
                    "400": {"description": "错误请求"}
                }
            }
        },
        "/api/{tp}/{name}/twoModel": {
            "post": {
                "summary": "特殊查询与采集",
                "parameters": [
                    {"name": "tp", "in": "path", "required": True, "schema": {"type": "string"}},
                    {"name": "name", "in": "path", "required": True, "schema": {"type": "string"},
                     "description": "get_ipadress | start_caiji | get_port"}
                ],
                "requestBody": {
                    "required": False,
                    "content": {
                        "application/json": {"schema": {"type": "object"}}
                    }
                },
                "responses": {"200": {"description": "成功"}}
            }
        },
        "/api/{name}/{start_time}/{end_time}/{number_range}/{ipvalue}/threeModel": {
            "post": {
                "summary": "按时间范围查询性能指标",
                "parameters": [
                    {"name": "name", "in": "path", "required": True, "schema": {"type": "string"},
                     "description": "cpuxinnengzhibiao | neicunxinnengzhibiao | cipanxinnengzhibiao | wangluoxinnengzhibiao"},
                    {"name": "start_time", "in": "path", "required": True, "schema": {"type": "string", "format": "date"}},
                    {"name": "end_time", "in": "path", "required": True, "schema": {"type": "string", "format": "date"}},
                    {"name": "number_range", "in": "path", "required": True, "schema": {"type": "string"}},
                    {"name": "ipvalue", "in": "path", "required": True, "schema": {"type": "string"}}
                ],
                "responses": {"200": {"description": "成功"}}
            }
        },
        "/api/fourModel": {
            "post": {
                "summary": "汇总最新系统性能数据",
                "responses": {"200": {"description": "成功"}}
            }
        },
        "/api/cmd/fourModel": {
            "post": {
                "summary": "执行命令（预设或自定义）",
                "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "properties": {
                    "ip": {"type": "string"},
                    "port": {"type": "integer"},
                    "defaultCmdString": {"type": "string"},
                    "cmdString": {"type": "string"}
                }}}}},
                "responses": {"200": {"description": "执行结果"}}
            }
        },
        "/api/return_cmd_four/": {
            "post": {"summary": "执行命令（同上）", "responses": {"200": {"description": "执行结果"}}}
        },
        "/api/fiveModel": {
            "post": {
                "summary": "IO/火焰图相关命令",
                "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "properties": {
                    "ip": {"type": "string"},
                    "port": {"type": "integer"},
                    "command": {"type": "string", "enum": ["get_flame_graph", "get_new_io_data", "get_io_stack"]}
                }}}}},
                "responses": {"200": {"description": "成功"}}
            }
        },
        "/api/sixModel": {
            "post": {
                "summary": "数据库信息/场景识别/存储信息",
                "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "properties": {
                    "type": {"type": "string", "enum": ["get_db", "get_db_info", "get_db_scene", "ceph_info"]},
                    "db": {"type": "string"},
                    "ip": {"type": "string"},
                    "port": {"type": "integer"}
                }}}}},
                "responses": {"200": {"description": "成功"}}
            }
        },
        "/api/userManager/{tp}": {
            "post": {
                "summary": "用户管理-增删改查",
                "parameters": [
                    {"name": "tp", "in": "path", "required": True, "schema": {"type": "string", "enum": ["create", "select", "update", "delete", "batchDelete"]}}
                ],
                "requestBody": {"required": False, "content": {"application/json": {"schema": {"type": "object"}}}},
                "responses": {"200": {"description": "成功"}}
            }
        },
        "/api/realtimeUpdatePidData": {
            "get": {
                "summary": "实时进程数据（Top前10）",
                "parameters": [
                    {"name": "ip", "in": "query", "required": True, "schema": {"type": "string"}},
                    {"name": "port", "in": "query", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {"200": {"description": "成功"}}
            }
        },
        "/api/pidInfo": {
            "post": {
                "summary": "进程信息/CPU亲和性设置",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/x-www-form-urlencoded": {
                            "schema": {"type": "object", "properties": {
                                "ip": {"type": "string"},
                                "port": {"type": "integer"},
                                "tp": {"type": "string", "enum": ["GETPIDINFO", "CHANGECPUID"]},
                                "changeCpuId": {"type": "string"},
                                "currPid": {"type": "string"}
                            }}
                        }
                    }
                },
                "responses": {"200": {"description": "成功"}}
            }
        },
        "/api/strategy/apply": {
            "post": {
                "summary": "应用策略包",
                "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "properties": {
                    "ip": {"type": "string"},
                    "port": {"type": "integer"},
                    "strategy": {"type": "string"}
                }, "required": ["ip", "port", "strategy"]}}}},
                "responses": {"200": {"description": "执行结果"}}
            }
        },
        "/api/ai_optimize/": {
            "post": {
                "summary": "AI 优化推理（直传直返）",
                "requestBody": {"required": False, "content": {"application/json": {"schema": {"type": "object", "properties": {
                    "question": {"type": "string"},
                    "q": {"type": "string"},
                    "text": {"type": "string"},
                    "prompt": {"type": "string"},
                    "stream": {"type": "boolean"}
                }}}}},
                "responses": {"200": {"description": "成功"}}
            }
        },
        "/api/execute_ai_strategy/": {
            "post": {
                "summary": "执行 AI 生成策略命令",
                "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "properties": {
                    "ip": {"type": "string"},
                    "port": {"type": "integer"},
                    "strategy": {"oneOf": [{"type": "string"}, {"type": "object"}]}
                }, "required": ["ip", "port", "strategy"]}}}},
                "responses": {"200": {"description": "执行结果"}}
            }
        },
        "/api/background_collection/": {
            "post": {
                "summary": "后台采集任务管理",
                "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "properties": {
                    "action": {"type": "string", "enum": ["start", "stop", "status", "cleanup", "force_stop_all", "test_connection"]},
                    "ip": {"type": "string"},
                    "port": {"type": "integer"},
                    "interval": {"type": "integer"},
                    "task_id": {"type": "string"}
                }, "required": ["action"]}}}},
                "responses": {"200": {"description": "成功"}}
            }
        },
        "/api/get_latest_data/": {
            "post": {
                "summary": "获取指定IP的最新性能数据",
                "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "properties": {
                    "ip": {"type": "string"},
                    "port": {"type": "integer"}
                }}}}},
                "responses": {"200": {"description": "成功"}}
            }
        },
        "/api/get_latest_data_simple/": {
            "get": {
                "summary": "获取最新性能数据（简化版）",
                "responses": {"200": {"description": "成功"}}
            }
        },
        "/api/save_collection_data/": {
            "post": {
                "summary": "保存采集数据（CPU/内存/磁盘/网络）",
                "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object"}}}},
                "responses": {"200": {"description": "成功"}}
            }
        },
        "/api/upload_log/": {
            "post": {
                "summary": "上传日志文件",
                "requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {"type": "object", "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "type": {"type": "string"},
                    "file": {"type": "string", "format": "binary"}
                }, "required": ["title", "file"]}}}},
                "responses": {"200": {"description": "成功"}}
            }
        },
        "/api/get_logs/": {
            "get": {"summary": "获取日志列表", "responses": {"200": {"description": "成功"}}}
        },
        "/api/view_log/{log_id}/": {
            "get": {
                "summary": "查看日志内容",
                "parameters": [
                    {"name": "log_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {"200": {"description": "成功"}, "404": {"description": "未找到"}}
            }
        },
        "/api/download_log/{log_id}/": {
            "get": {
                "summary": "下载日志文件",
                "parameters": [
                    {"name": "log_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {"200": {"description": "文件流"}, "404": {"description": "未找到"}}
            }
        },
        "/api/delete_log/{log_id}/": {
            "delete": {
                "summary": "删除日志记录",
                "parameters": [
                    {"name": "log_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {"200": {"description": "成功"}, "404": {"description": "未找到"}}
            }
        },
        "/api/create_direct_log/": {
            "post": {
                "summary": "直接创建日志记录",
                "requestBody": {"required": True, "content": {"application/x-www-form-urlencoded": {"schema": {"type": "object", "properties": {
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                    "type": {"type": "string"}
                }, "required": ["title", "content"]}}}},
                "responses": {"200": {"description": "成功"}}
            }
        },
        "/api/user_info": {
            "get": {"summary": "获取当前登录用户", "responses": {"200": {"description": "成功"}}}
        },
        "/no_cache_image/{image_name}/": {
            "get": {
                "summary": "获取图片（二进制）",
                "parameters": [
                    {"name": "image_name", "in": "path", "required": True, "schema": {"type": "string"}}
                ],
                "responses": {"200": {"description": "图片二进制数据"}, "404": {"description": "未找到"}}
            }
        }
    }
}


def openapi_schema(request):
    return JsonResponse(OPENAPI_SPEC)


@csrf_exempt
def swagger_ui(request):
    html = """
<!DOCTYPE html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <title>KyLin API Docs</title>
  <link rel=\"stylesheet\" href=\"https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css\" />
  <style>body { margin: 0; } #swagger-ui { height: 100vh; }</style>
</head>
<body>
  <div id=\"swagger-ui\"></div>
  <script src=\"https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js\"></script>
  <script>
    window.onload = () => {
      window.ui = SwaggerUIBundle({
        url: '/api/openapi.json',
        dom_id: '#swagger-ui',
        presets: [SwaggerUIBundle.presets.apis],
        layout: 'BaseLayout'
      });
    };
  </script>
</body>
</html>
"""
    return HttpResponse(html) 