#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KyLin系统优化API视图
"""

import os
import json
import time
import uuid
import logging
import requests
import traceback
import datetime
from datetime import timezone
from django.utils import timezone as django_timezone
import re

# 配置日志
logger = logging.getLogger(__name__)



# Django相关导入
from ..models import *
from django.views import View
from django.http import Http404
from ..model.SocketServer import select_client
from ..model.DBSence import dbSceneRecognition
from django.forms.models import model_to_dict
from django.views.decorators.csrf import csrf_exempt
from django.http.response import HttpResponse, JsonResponse
from ..utils import encrypt
from kylinApp.util import dict_to_custom_str
from ..utils.background_tasks import task_manager
from django.conf import settings
from kylinApp.models import (
    UserModels, MonitoringServerInformation, DataBaseInformationManagement,
    ServerManagement, CPUPerformanceMetrics, MemoryPerformanceMetrics,
    DiskPerformanceMetrics, NetworkPerformanceMetrics, AdditionalInformation,
    LogRecord
)






# 策略包接口（场景化）
STRATEGY_PACKS = {
        "db_speedup": [
            "command:添加数据库缓存",
            "command:优化文件系统",
            "command:重启MySQL服务",
            "command:查看磁盘使用情况"
        ],
        "io_optimize": [
            "command:清理系统缓存",
            "command:查看磁盘使用情况",
            "command:查看活跃连接数",
            "command:查看运行进程"
        ],
        "security_harden": [
            "command:查看防火墙",
            "command:开启防火墙",
            "command:启用SYN Cookie",
            "command:关闭NTP同步服务器",
            "command:查看当前登录用户"
        ],
        "memory_release": [
            "command:清理系统缓存",
            "command:查看内存使用情况",
            "command:查看运行进程"
        ],
        "service_restart": [
            "command:重启Nginx服务",
            "command:重启MySQL服务",
            "command:重启Docker服务"
        ],
        "network_optimize": [
            "command:检测网络连接状态",
            "command:查看端口占用情况",
            "command:终止占用端口的进程",
            "command:查看活跃连接数"
        ],
        "system_health_check": [
            "command:查看系统负载",
            "command:查看CPU信息",
            "command:查看内核日志",
            "command:检查系统内核日志",
            "command:导出当前系统状态"
        ],
        "resource_release": [
            "command:清理系统缓存",
            "command:查看内存使用情况",
            "command:查看磁盘使用情况",
            "command:查看运行进程"
        ],
        "server_reboot": [
            "command:重启服务器"
        ]}
# 策略包接口
@csrf_exempt
def apply_strategy(request):
    data = json.loads(request.body.decode("utf8"))
    ip = data.get("ip")
    port = int(data.get("port"))
    strategy = data.get("strategy")
    commands = STRATEGY_PACKS.get(strategy, [])
    results = []
    for cmd in commands:
        result = select_client.send_command(cmd, ip, port)
        results.append({ "command": cmd, "result": result })
    return JsonResponse({ "message": "success", "results": results }, status=200)
def create_data(dbmodel, data):
    try:
        # 处理服务信息管理的字段映射
        if dbmodel.__name__ == 'ServerManagement':
            # 映射前端字段名到模型字段名
            if 'severCategory' in data:
                data['server_category'] = data.pop('severCategory')
            if 'remark' in data:
                data['remarks'] = data.pop('remark')

        # 处理监控服务器信息管理的字段映射
        elif dbmodel.__name__ == 'MonitoringServerInformation':
            # 字段映射：前端字段名 -> 模型字段名
            if 'serviceType' in data:
                data['server_category'] = data.pop('serviceType')
            if 'severCategory' in data:
                data['server_category'] = data.pop('severCategory')
            
            # 移除不属于模型的字段
            allowed_fields = ['ip', 'port', 'server_category', 'remarks']
            filtered_data = {k: v for k, v in data.items() if k in allowed_fields}
            data = filtered_data

            # 验证必填字段
            if not data.get('ip'):
                raise ValueError("IP地址不能为空")
            if not data.get('port'):
                raise ValueError("端口不能为空")

            # 确保端口是整数
            if 'port' in data:
                try:
                    data['port'] = int(data['port'])
                    if data['port'] < 1 or data['port'] > 65535:
                        raise ValueError("端口号必须在1-65535之间")
                except (ValueError, TypeError):
                    raise ValueError("端口号必须是有效的数字")

            # 确保服务类型和备注字段存在
            if 'server_category' not in data or data['server_category'] is None:
                data['server_category'] = ""
            if 'remarks' not in data or data['remarks'] is None:
                data['remarks'] = ""

        print(f"Creating {dbmodel.__name__} with data: {data}")
        dbmodel.objects.create(**data)
        print(f"Successfully created {dbmodel.__name__}")
    except Exception as e:
        print(f"Error creating {dbmodel.__name__}: {e}")
        print(f"Data: {data}")
        raise e


def select_data(dbmodel, data):
    condition = data
    query = dbmodel.objects.filter(**condition)
    return query


def select_all_data(dbmodel):
    query = dbmodel.objects.all()
    return query


def update_data(dbmodel, data):
    try:
        # 检查数据类型，如果已经是字典则直接使用，否则解析JSON
        if isinstance(data["old"], str):
            old = json.loads(data["old"])
        else:
            old = data["old"]

        if isinstance(data["new"], str):
            new = json.loads(data["new"])
        else:
            new = data["new"]

        print(f"原始更新数据 - 旧数据: {old}")
        print(f"原始更新数据 - 新数据: {new}")

        # 处理服务信息管理的字段映射
        if dbmodel.__name__ == 'ServerManagement':
            # 映射前端字段名到模型字段名
            for data_dict in [old, new]:
                if 'severCategory' in data_dict:
                    data_dict['server_category'] = data_dict.pop('severCategory')
                if 'remark' in data_dict:
                    data_dict['remarks'] = data_dict.pop('remark')

        # 处理监控服务器信息管理的字段映射
        elif dbmodel.__name__ == 'MonitoringServerInformation':
            # 字段映射：前端字段名 -> 模型字段名
            for data_dict in [old, new]:
                if 'serviceType' in data_dict:
                    data_dict['server_category'] = data_dict.pop('serviceType')
                if 'severCategory' in data_dict:
                    data_dict['server_category'] = data_dict.pop('severCategory')
            
            # 移除不属于模型的字段
            allowed_fields = ['ip', 'port', 'server_category', 'remarks']
            for data_dict in [old, new]:
                filtered_data = {k: v for k, v in data_dict.items() if k in allowed_fields}
                data_dict.clear()
                data_dict.update(filtered_data)

                # 验证必填字段
                if not data_dict.get('ip'):
                    raise ValueError("IP地址不能为空")
                if not data_dict.get('port'):
                    raise ValueError("端口不能为空")

                # 确保端口是整数
                if 'port' in data_dict:
                    try:
                        data_dict['port'] = int(data_dict['port'])
                        if data_dict['port'] < 1 or data_dict['port'] > 65535:
                            raise ValueError("端口号必须在1-65535之间")
                    except (ValueError, TypeError):
                        raise ValueError("端口号必须是有效的数字")

                # 确保备注字段存在
                if 'remarks' not in data_dict or data_dict['remarks'] is None:
                    data_dict['remarks'] = ""

        print(f"处理后更新数据 - 旧数据: {old}")
        print(f"处理后更新数据 - 新数据: {new}")
    except Exception as e:
        print(f"数据处理错误: {e}")
        raise e

    try:
        # 处理remarks字段的空字符串和None值匹配，并排除密码字段
        old_without_password = {k: v for k, v in old.items() if k != "password"}

        print(f"查询条件: {old_without_password}")

        if "remarks" in old_without_password and old_without_password["remarks"] == "":
            # 如果旧数据中remarks是空字符串，则查询时排除remarks字段或使用None
            old_without_remarks = {k: v for k, v in old_without_password.items() if k != "remarks"}
            query = dbmodel.objects.filter(**old_without_remarks)
            # 进一步过滤remarks为None或空字符串的记录
            query = query.filter(remarks__isnull=True) | query.filter(remarks="")
        else:
            query = dbmodel.objects.filter(**old_without_password)

        print(f"查询结果数量: {query.count()}")

        if query.exists():
            # 更新时也排除密码字段，除非新数据中的密码不是******
            new_without_password = {k: v for k, v in new.items() if k != "password" or v != "******"}
            print(f"更新数据: {new_without_password}")
            result = query.update(**new_without_password)
            print(f"更新结果: {result} 条记录被更新")
        else:
            print("未找到匹配的记录")
            # 尝试更宽松的查询（只用IP和端口）
            if 'ip' in old and 'port' in old:
                fallback_query = dbmodel.objects.filter(ip=old['ip'], port=old['port'])
                print(f"备用查询结果数量: {fallback_query.count()}")
                if fallback_query.exists():
                    new_without_password = {k: v for k, v in new.items() if k != "password" or v != "******"}
                    result = fallback_query.update(**new_without_password)
                    print(f"备用更新结果: {result} 条记录被更新")
                else:
                    print("备用查询也未找到匹配的记录")
    except Exception as e:
        print(f"更新操作错误: {e}")
        raise e


def back_del_message(query):
    if query:
        query.delete()
        return "删除成功"
    return "无效IP地址"


def zeng_shan_gai_cha_one_tool(tp, number_range, db_model, data):
    try:
        # 模块一
        if tp == "create":
            create_data(db_model, data)
            return HttpResponse("新建成功", status=200)
        elif tp == "del":
            query = select_data(db_model, data=data)
            return HttpResponse(back_del_message(query), status=200)
        elif tp == "select":
            query = select_data(db_model, data=data)
            data_dicts = constrain_the_page(number_range, query)
            return JsonResponse(data_dicts, status=200)
        elif tp == "update":
            update_data(db_model, data)
            return HttpResponse("更新成功", status=200)
    except Exception as e:
        logger.error(f"Error in zeng_shan_gai_cha_one_tool: {e}")
        return JsonResponse({
            "error": str(e),
            "message": "操作失败"
        }, status=500)


def cha_two_tool(name, dbmodel, data, tp=""):
    try:
        if name == "get_ipadress":
            logger.info("开始获取IP地址列表")
            try:
                query = select_all_data(dbmodel)
                logger.info(f"查询到 {len(query)} 条服务器记录")
                
                # 修改：返回备注而不是IP地址，但保留IP作为值
                ip_remarks = {}
                for item in query:
                    # 使用备注作为显示文本，IP作为值
                    display_text = item.remarks if hasattr(item, 'remarks') and item.remarks else item.ip
                    ip_remarks[display_text] = item.ip
                    logger.info(f"服务器: {display_text} -> {item.ip}")
                
                logger.info(f"返回IP地址数据: {ip_remarks}")
                return JsonResponse(ip_remarks, status=200)
            except Exception as e:
                logger.error(f"获取IP地址列表失败: {e}")
                import traceback
                traceback.print_exc()
                return JsonResponse({
                    "error": f"获取IP地址列表失败: {str(e)}"
                }, status=500)
        elif name == "start_caiji":
            try:
                # 解析并规范化 IP
                ip_raw = data.get("ip")
                if not ip_raw:
                    return JsonResponse({
                        "error": "IP参数不能为空"
                    }, status=400)

                ip_candidate = str(ip_raw).strip()
                ip_match = re.search(r"(\d{1,3}(?:\.\d{1,3}){3})", ip_candidate)
                if ip_match:
                    host = ip_match.group(1)
                else:
                    # 尝试用备注反查IP
                    remark = ip_candidate.split("(")[0].strip()
                    remark_qs = select_data(dbmodel, {"remarks": remark})
                    if remark_qs and remark_qs.count() > 0:
                        host = remark_qs.first().ip
                    else:
                        return JsonResponse({
                            "error": f"未找到可用的IP: {ip_raw}"
                        }, status=404)

                # 解析端口
                port_raw = data.get("port")
                if port_raw in (None, ""):
                    return JsonResponse({
                        "error": "端口参数不能为空"
                    }, status=400)
                try:
                    port = int(port_raw)
                except (TypeError, ValueError):
                    return JsonResponse({
                        "error": f"端口格式不正确: {port_raw}"
                    }, status=400)

                # 发起采集
                try:
                    result = select_client.get_info(host, port, tp)
                    return JsonResponse(result, status=200)
                except Exception as e:
                    logger.error(f"采集数据失败({host}:{port}): {e}")
                    return JsonResponse({
                        "error": f"采集数据失败: {str(e)}"
                    }, status=500)
            except Exception as e:
                logger.error(f"start_caiji 参数处理异常: {e}")
                return JsonResponse({
                    "error": f"参数处理异常: {str(e)}"
                }, status=500)
        elif name == "get_port":
            try:
                # 数据已经在return_data_model_two中解析过了
                logger.info(f"get_port 接收到的数据: {data}")
                
                ip_raw = data.get("ip")
                if not ip_raw:
                    logger.error("IP参数为空")
                    return JsonResponse({
                        "error": "IP参数不能为空"
                    }, status=400)
                
                # 规范化IP：支持 "备注 (IP)" 或仅备注 的传参
                ip_candidate = str(ip_raw).strip()
                ip_match = re.search(r"(\d{1,3}(?:\.\d{1,3}){3})", ip_candidate)
                if ip_match:
                    ip = ip_match.group(1)
                else:
                    # 尝试用备注反查IP
                    remark = ip_candidate.split("(")[0].strip()
                    logger.info(f"根据备注反查IP: remark={remark}")
                    remark_qs = select_data(dbmodel, {"remarks": remark})
                    if remark_qs and remark_qs.count() > 0:
                        ip = remark_qs.first().ip
                    else:
                        # 无法解析出有效IP
                        logger.error(f"无法从参数中解析出有效IP: {ip_raw}")
                        return JsonResponse({
                            "error": f"未找到IP {ip_raw} 的端口信息"
                        }, status=404)
                
                logger.info(f"查询IP: {ip} 的端口信息")
                
                # 查询指定IP的端口信息 - 使用正确的字段名 'ip'
                query = select_data(dbmodel, {"ip": ip})
                logger.info(f"查询结果数量: {query.count()}")
                
                if not query:
                    logger.error(f"未找到IP {ip} 的端口信息")
                    return JsonResponse({
                        "error": f"未找到IP {ip} 的端口信息"
                    }, status=404)
                
                # 返回端口列表
                ports = [item.port for item in query if hasattr(item, 'port')]
                port_dict = {}
                for i, port in enumerate(ports):
                    port_dict[f"port_{i}"] = port
                
                # 同时返回数组形式，便于前端直接使用
                response_payload = {"port": ports}
                response_payload.update(port_dict)
                
                logger.info(f"为IP {ip} 找到端口: {response_payload}")
                return JsonResponse(response_payload, status=200)
            except Exception as e:
                logger.error(f"获取端口信息失败: {e}")
                import traceback
                traceback.print_exc()
                return JsonResponse({
                    "error": f"获取端口信息失败: {str(e)}"
                }, status=500)
        else:
            return JsonResponse({
                "error": f"未知的操作类型: {name}"
            }, status=400)
    except Exception as e:
        logger.error(f"cha_two_tool函数异常: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            "error": f"服务器内部错误: {str(e)}"
        }, status=500)


# 约束页面
def constrain_the_page(number_range, filtered_records):
    # 约束取值范围数据最长长度
    page_content_number = 50
    start_index, end_index = map(int, number_range.split("-"))
    start_index -= 1
    max_len = len(filtered_records)
    # 是50的几倍
    all_numb, a_mod = divmod(max_len, page_content_number)
    max_numb, m_mod = divmod(start_index, page_content_number)

    if all_numb >= max_numb:
        filtered_records = filtered_records[start_index:end_index]
    elif all_numb < max_numb:
        start_index = all_numb * page_content_number
        filtered_records = filtered_records[start_index:]

    data_dicts = {"all_data": [], "max_len": max_len, "all_numb": all_numb, "a_mod": a_mod, "page": page_content_number,
                  "range": number_range}
    for record in filtered_records:
        data_dict = model_to_dict(record)
        if "password" in data_dict:
            data_dict["password"] = "******"
        # 处理remarks字段的None值
        if "remarks" in data_dict and data_dict["remarks"] is None:
            data_dict["remarks"] = ""
        data_dicts["all_data"].append(data_dict)
    return data_dicts


@csrf_exempt
def return_data_model_one(request, name, tp, number_range):
    """
    :param request:
    :param name: 决定用那张数据表进行查询，前端必须返回model_form里面数据表对应的名字
    :param tp: 决定增删还是改查
    :param number_range
    :return:
    """
    # print(name, tp, number_range)
    data = json.loads(request.body.decode("utf8"))
    # print(data)
    if name == "JianKongFuWuQi":
        return zeng_shan_gai_cha_one_tool(tp, number_range, MonitoringServerInformation, data)
    elif name == "JianKongShuJuKu":
        return zeng_shan_gai_cha_one_tool(tp, number_range, DataBaseInformationManagement, data)
    elif name == "FuWuXinXi":
        return zeng_shan_gai_cha_one_tool(tp, number_range, ServerManagement, data)
    return JsonResponse({"state": "no"}, status=500)


@csrf_exempt
def return_data_model_two(request, tp, name):
    " ip地址"
    data = ""
    if name != "get_ipadress":
        try:
            data = json.loads(request.body.decode("utf8"))
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析错误: {e}")
            return JsonResponse({
                "error": "请求数据格式错误"
            }, status=400)
    return cha_two_tool(name, MonitoringServerInformation, data, tp)


@csrf_exempt
def return_data_model_three(request, name, start_time, end_time, number_range, ipvalue):

    start_time = datetime.datetime.strptime(start_time, '%Y-%m-%d')
    end_time = datetime.datetime.strptime(end_time, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
    condition = {}
    if ipvalue != "no":
        condition.update({"ipaddress": ipvalue})
    if name == "cpuxinnengzhibiao":
        records = select_data(CPUPerformanceMetrics, condition)
    elif name == "neicunxinnengzhibiao":
        records = select_data(MemoryPerformanceMetrics, condition)
    elif name == "cipanxinnengzhibiao":
        records = select_data(DiskPerformanceMetrics, condition)
    elif name == "wangluoxinnengzhibiao":
        records = select_data(NetworkPerformanceMetrics, condition)
    else:
        return JsonResponse({"error": "Invalid name parameter"}, status=400,)
    # 过滤时间范围
    filtered_records = []
    for record in records:
        # 使用 parse_date 将字符串转换为 date 对象
        current_date = datetime.datetime.fromisoformat(str(record.currentTime))
        # 移除时区信息以保持一致性
        if current_date.tzinfo is not None:
            current_date = current_date.replace(tzinfo=None)
        if current_date and start_time <= current_date <= end_time:
            filtered_records.append(record)

    data_dicts = constrain_the_page(number_range, filtered_records)
    # 输出过滤后的结果
    for record in data_dicts["all_data"]:
        record["currentTime"] = record["currentTime"].strftime('%Y-%m-%d %H:%M:%S')
    return JsonResponse(data_dicts)


@csrf_exempt
def return_data_model_four(request):
    data = {}
    cpu_data = select_all_data(CPUPerformanceMetrics)
    disk_data = select_all_data(DiskPerformanceMetrics)
    memory_data = select_all_data(MemoryPerformanceMetrics)
    network_data = select_all_data(NetworkPerformanceMetrics)
    os_data = select_all_data(AdditionalInformation)
    if cpu_data:
        cpu_percent = cpu_data.last().percent
        data.update({"cpu_percent": cpu_percent})
    if disk_data:
        disk_percent = disk_data.last().percent
        data.update({"disk_percent": disk_percent})
    if memory_data:
        memory_percent = memory_data.last().percent
        data.update({"memory_percent": memory_percent})
    if network_data:
        network_info = network_data.last()
        data.update({"network_data": {"sent": network_info.sent, "recv": network_info.recv}})
    if os_data:
        os_info = os_data.last()
        data.update({"os_data": {"os_name": os_info.os_name,
                                 "os_info": os_info.os_info,
                                 "os_version": os_info.os_version,
                                 "os_processor_architecture": os_info.os_processor_architecture,
                                 "os_processor_name": os_info.os_processor_name}})
    return JsonResponse(data, status=200)


@csrf_exempt
def return_cmd_four(request):
    # 在 api.py 顶部添加

    choice_cmd = {
        "1": "command:查看防火墙",
        "2": "command:开启防火墙",
        "3": "command:关闭防火墙",
        "4": "command:优化文件系统",
        "5": "command:关闭NTP同步服务器",
        "6": "command:查看NTP同步服务器",
        "7": "command:开启NTP同步服务器",
        "10": "command:启用SYN Cookie",
        "11": "command:备份数据库 aa",
        "12": "command:添加数据库缓存",
        "13": "command:查看时间同步",
        "14": "command:设置NTP",
        "15": "slove_su",
        "16": "slove_system_jam",
        # 新增常用指令
        "17": "command:查看当前登录用户",
        "18": "command:清理系统缓存",
        "19": "command:查看磁盘使用情况",
        "20": "command:重启Nginx服务",
        "21": "command:检查系统内核日志",
        "22": "command:查看系统负载",
        "23": "command:查看内存使用情况",
        "24": "command:查看CPU信息",
        "25": "command:重启服务器",
        "26": "command:重启MySQL服务",
        "27": "command:检测网络连接状态",
        "28": "command:查看端口占用情况",
        "29": "command:终止占用端口的进程",
        "30": "command:查看活跃连接数",
        "31": "command:重启Docker服务",
        "32": "command:查看内核日志",
        "33": "command:检查CPU绑定情况",
        "34": "command:查看运行进程",
        "35": "command:导出当前系统状态"
    }
    choice_empty_info = {
        "2": "The firewall is successfully enabled",
        "3": "The firewall was successfully shut down",
        "5": "The NTP synchronization server was successfully shut down",
        "7": "The NTP synchronization server is enabled",
        "11": "The backup database succeeded load /backupfile.sql",
        "12": "query cache size=600000",
        "23": "Nginx has been restarted",
        "25": "Server is rebooting...",
        "26": "MySQL has been restarted",
        "31": "Docker service restarted successfully"
    }

    data = json.loads(request.body.decode("utf8"))
    ip = data.get("ip")
    port = int(data.get("port"))
    defaultcmd = data.get("defaultCmdString")
    command = data.get("cmdString")
    
    # 添加调试信息
    print(f"API接收到的数据: {data}")
    print(f"IP: {ip}, Port: {port}")
    print(f"defaultcmd: {defaultcmd}, command: {command}")
    print(f"choice_cmd.get(defaultcmd): {choice_cmd.get(defaultcmd) if defaultcmd else 'None'}")
    
    # if command in ["15", "16"]:
    #     state_info = select_client.send_command(f"command:{command}", ip, port)
    if command != "0":
        # 自动补全前缀
        cmd_to_send = command if command.startswith("command:") else "command:" + command
        print(f"发送自定义命令: {cmd_to_send}")
        state_info = select_client.send_command(cmd_to_send, ip, port)
    else:
        actual_command = choice_cmd.get(defaultcmd)
        print(f"发送预设命令: {actual_command}")
        state_info = select_client.send_command(actual_command, ip, port)
    
    print(f"命令执行结果: {state_info}")
    
    if not state_info or state_info == '""':
        state_info = choice_empty_info.get(defaultcmd)
        print(f"使用默认响应: {state_info}")
    
    return HttpResponse(str(state_info), status=200)


# 实则模块6
@csrf_exempt
def return_data_five(request):
    data = json.loads(request.body.decode("utf8"))
    ip = data.get("ip")
    port = int(data.get("port"))
    command = data.get("command")
    if command == "get_flame_graph":
        select_client.send_command("get_flame_graph", ip, port)
    elif command == "get_new_io_data":
        info = select_client.send_command("command:get_biotop", ip, port)
        return HttpResponse(info, status=200)
    elif command == "get_io_stack":
        info = select_client.send_command("command:get_io_stack", ip, port)
        return HttpResponse(info, status=200)
    return JsonResponse({"state": "ok"}, status=200)


# 火焰图转成二进制
class NoCacheImageView(View):
    def get(self, request, *args, **kwargs):
        image_name = kwargs.get('image_name')
        image_path = os.path.join('kylinApp', 'static', 'img', f'{image_name}')  # 替换为你的图片路径
        if not os.path.exists(image_path):
            raise Http404("Image does not exist")
        with open(image_path, mode="rb") as f:
            return HttpResponse(f.read(), status=200)


# 实则模块5
@csrf_exempt
def return_data_six(request):
    data = json.loads(request.body.decode("utf8"))
    tp = data.get("type")
    ip = data.get("ip")
    port = data.get("port")
    if tp == "get_db":
        query = select_all_data(DataBaseInformationManagement)
        if query:
            data = {"database": [item.database for item in query]}
        return JsonResponse(data, status=200)
    elif tp == "get_db_info":
        condition = {
            "database": data.get("db")
        }
        query = select_data(DataBaseInformationManagement, condition)
        if query:
            data = {"info": {"dbtype": [], 'ip': [], "port": []}}
            for item in query:
                data["info"]["dbtype"].append(item.type)
                data["info"]["ip"].append(item.ip)
                data["info"]["port"].append(item.port)
        return JsonResponse(data, status=200)
    elif tp == "get_db_scene":
        condition = {
            "database": data.get("db")
        }
        query = select_data(DataBaseInformationManagement, condition)[0]
        values = dbSceneRecognition.return_data_main(query.ip, query.user, query.password,
                                                     query.database, query.port, query.code)
        return JsonResponse(values, status=200)
    elif tp == "ceph_info":
        data = select_client.get_info(ip, int(port), tp)
        return JsonResponse(data)
    return HttpResponse("请求错误", status=303)


@csrf_exempt
def userManager(request, tp):
    data = json.loads(request.body.decode('utf-8'))
    if tp == "select":
        user_name = data.get("userName", {})
        filter = {}
        if user_name:
            filter["username"] = user_name
        user_info = list(UserModels.objects.filter(**filter).values())
        for user in user_info:
            user["password"] = "********"
        return JsonResponse({"message": "success", "data": user_info}, status=200)
    elif tp == "create":
        user_name = data.get("username", "")
        password = data.get("password", "")
        encrypt_password = encrypt.encrypt_md5(password)
        if UserModels.objects.filter(username=user_name).exists():
            return JsonResponse({"message": "用户已存在"}, status=200)
        else:
            UserModels.objects.create(username=user_name, password=encrypt_password)
            return JsonResponse({"message": "success"}, status=200)
    elif tp == "delete":
        user_name = data.get("username", "")
        UserModels.objects.filter(username=user_name).delete()
        return JsonResponse({"message": "success"}, status=200)
    elif tp == "batchDelete":
        usernames = data.get("usernames", [])
        logger.info(f"批量删除请求 - 接收到的用户名列表: {usernames}")
        
        if not usernames:
            logger.warning("批量删除失败 - 用户名列表为空")
            return JsonResponse({"message": "用户名列表不能为空"}, status=400)
        
        try:
            # 检查用户是否存在
            existing_users = list(UserModels.objects.filter(username__in=usernames).values_list('username', flat=True))
            logger.info(f"找到的用户: {existing_users}")
            
            # 批量删除用户
            deleted_count = UserModels.objects.filter(username__in=usernames).delete()[0]
            logger.info(f"成功删除 {deleted_count} 个用户")
            
            return JsonResponse({
                "message": "success", 
                "deleted_count": deleted_count,
                "deleted_usernames": usernames,
                "existing_users": existing_users
            }, status=200)
        except Exception as e:
            logger.error(f"批量删除异常: {e}")
            return JsonResponse({"message": f"批量删除失败: {str(e)}"}, status=500)
    elif tp == "update":
        try:
            # 检查新的数据格式
            if "username" in data and "userData" in data:
                # 新格式：直接使用username和userData
                username = data["username"]
                new_data = data["userData"]
                
                # 查找用户
                try:
                    user = UserModels.objects.get(username=username)
                    
                    # 更新用户信息
                    if "email" in new_data:
                        user.email = new_data["email"]
                    if "gender" in new_data:
                        user.gender = new_data["gender"]
                    if "userType" in new_data:
                        user.userType = new_data["userType"]
                    if "status" in new_data:
                        user.status = new_data["status"]
                    if "password" in new_data and new_data["password"]:
                        encrypt_password = encrypt.encrypt_md5(new_data["password"])
                        user.password = encrypt_password
                    
                    user.save()
                    return JsonResponse({"message": "success"}, status=200)
                except UserModels.DoesNotExist:
                    return JsonResponse({"message": "用户不存在"}, status=400)
            else:
                # 旧格式：使用old和new
                old_value = data.get("old", {})
                new_value = data.get("new", {})
                
                # 如果old和new是字符串，则解析它们
                if isinstance(old_value, str):
                    old_value = json.loads(old_value)
                if isinstance(new_value, str):
                    new_value = json.loads(new_value)
                
                new_user_name = new_value.get("username", "")
                new_password = new_value.get("password", "")
                encrypt_password = encrypt.encrypt_md5(new_password)
                UserModels.objects.filter(username=new_user_name).update(password=encrypt_password)

                return JsonResponse({"message": "success"}, status=200)
        except Exception as e:
            return JsonResponse({"message": f"更新失败: {str(e)}"}, status=500)
    return HttpResponse("地址请求成功")

def realtime_update_pid_data(request):
    """更新进程数据 """
    try:
        ip = request.GET.get('ip')
        port = request.GET.get('port')
        
        # 参数验证
        if not ip or not port:
            return JsonResponse({
                "message": "error",
                "error": "IP和端口参数不能为空"
            }, status=400)
        
        # 验证端口是否为有效数字
        try:
            port_int = int(port)
            if port_int <= 0 or port_int > 65535:
                return JsonResponse({
                    "message": "error", 
                    "error": "端口号必须在1-65535范围内"
                }, status=400)
        except ValueError:
            return JsonResponse({
                "message": "error",
                "error": "端口号必须是有效的数字"
            }, status=400)
        
        data = select_client.send_command("get_top", ip, port_int)
        json_data = json.loads(data)
        # 将字典转换为列表，以便筛选和排序
        data_list = list(json_data.values())

        # 筛选出 %CPU 和 %MEM 不等于 0 的数据
        filtered_data = [item for item in data_list if float(item['%CPU']) > 0 or float(item['%MEM']) > 0.1]

        # 按 %CPU 降序排序
        sorted_by_cpu = sorted(filtered_data, key=lambda x: float(x['%CPU']), reverse=True)

        data = {}
        if len(sorted_by_cpu) > 10:
            for item in sorted_by_cpu[:10]:
                PID = item.pop("PID")
                data[PID] = item
        else:
            for item in sorted_by_cpu:
                PID = item.pop("PID")
                data[PID] = item
        return JsonResponse({
            "message": "success",
            "data": data
        }, status=200)
    except Exception as e:
        logger.error(f"realtime_update_pid_data error: {e}")
        return JsonResponse({
            "message": "error",
            "error": f"获取进程数据失败: {str(e)}"
        }, status=500)

@csrf_exempt
def pid_info(request):
    ip = request.POST.get("ip")
    port = request.POST.get("port")
    tp = request.POST.get("tp")
    changeCpuId = request.POST.get("changeCpuId")
    currPid = request.POST.get("currPid")
    if tp == "GETPIDINFO":
        data = select_client.send_command("get_ps",ip, int(port))
        json_data = json.loads(data)
        json_data["CPUCount"] = [hex(i) for i in set(json_data["CPU核心"])]
        json_data["CPU核心"] = [hex(i) for i in json_data["CPU核心"]]
        return JsonResponse({
            "message": "success",
            "data": json_data
        }, status=200)
    elif tp == "CHANGECPUID":
        data = select_client.send_command("set_cpu_affinity", ip,int(port), changeCpuId, currPid)
        return JsonResponse({"message": "success"}, status=200)





@csrf_exempt
def background_collection_api(request):
    """后台采集任务管理接口"""
    try:
        # 记录请求信息
        logger.info(f"收到后台采集任务请求: {request.method}")
        
        if request.method != 'POST':
            logger.warning(f"不支持的请求方法: {request.method}")
            return JsonResponse({
                "success": False,
                "message": f"不支持的请求方法: {request.method}"
            }, status=405)
        
        # 解析请求数据
        try:
            data = json.loads(request.body.decode("utf8"))
            logger.info(f"请求数据: {data}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            return JsonResponse({
                "success": False,
                "message": f"JSON解析失败: {str(e)}"
            }, status=400)
        
        action = data.get("action")
        logger.info(f"执行操作: {action}")
        
        if action == "start":
            # 启动后台采集任务
            ip = data.get("ip")
            port = int(data.get("port"))
            interval = int(data.get("interval", 30))
            task_id = f"{ip}_{port}_{int(time.time())}"
            
            success, message = task_manager.start_collection_task(task_id, ip, port, interval)
            
            return JsonResponse({
                "success": success,
                "message": message,
                "task_id": task_id if success else None
            })
            
        elif action == "stop":
            # 停止后台采集任务
            task_id = data.get("task_id")
            logger.info(f"尝试停止任务: {task_id}")
            
            if not task_id:
                logger.warning("停止任务请求缺少任务ID")
                return JsonResponse({
                    "success": False,
                    "message": "缺少任务ID"
                }, status=400)
            
            try:
                success, message = task_manager.stop_collection_task(task_id)
                logger.info(f"停止任务结果: success={success}, message={message}")
                
                return JsonResponse({
                    "success": success,
                    "message": message
                })
            except Exception as e:
                logger.error(f"停止任务时发生异常: {e}")
                return JsonResponse({
                    "success": False,
                    "message": f"停止任务时发生异常: {str(e)}"
                }, status=500)
            
        elif action == "status":
            # 获取任务状态
            task_id = data.get("task_id")
            if task_id:
                # 先清理已停止的任务
                task_manager.cleanup_stopped_tasks()
                
                status = task_manager.get_task_status(task_id)
                if status is None:
                    return JsonResponse({
                        "success": False,
                        "message": "任务不存在"
                    }, status=404)
                return JsonResponse({
                    "success": True,
                    "status": status
                })
            else:
                # 返回所有任务
                tasks = task_manager.get_all_tasks()
                return JsonResponse({
                    "success": True,
                    "tasks": tasks
                })
        
        elif action == "cleanup":
            # 清理已停止的任务
            task_id = data.get("task_id")
            if task_id:
                task_manager.cleanup_task(task_id)
                return JsonResponse({
                    "success": True,
                    "message": "任务已清理"
                })
            else:
                # 清理所有已停止的任务
                task_manager.cleanup_stopped_tasks()
                return JsonResponse({
                    "success": True,
                    "message": "所有已停止任务已清理"
                })
        
        elif action == "force_stop_all":
            # 强制停止所有任务
            logger.warning("执行操作: force_stop_all")
            try:
                stopped_count = task_manager.force_stop_all_tasks()
                return JsonResponse({
                    "success": True,
                    "message": f"已强制停止并清理 {stopped_count} 个任务"
                })
            except Exception as e:
                logger.error(f"强制停止所有任务失败: {e}")
                return JsonResponse({
                    "success": False,
                    "message": f"强制停止失败: {str(e)}"
                }, status=500)
        elif action == "test_connection":
            # 测试探针连接
            ip = data.get("ip")
            port = data.get("port")
            if not ip or not port:
                return JsonResponse({
                    "success": False,
                    "message": "缺少IP或端口参数"
                }, status=400)
            
            try:
                # 测试CPU数据获取
                cpu_data = select_client.get_info(ip, int(port), 'cpu')
                return JsonResponse({
                    "success": True,
                    "message": "探针连接成功",
                    "data": cpu_data
                })
            except Exception as e:
                logger.error(f"探针连接测试失败: {e}")
                return JsonResponse({
                    "success": False,
                    "message": f"探针连接失败: {str(e)}"
                }, status=500)
        
        else:
            return JsonResponse({
                "success": False,
                "message": "无效的操作"
            }, status=400)
            
    except json.JSONDecodeError as e:
        return JsonResponse({
            "success": False,
            "message": f"JSON解析失败: {str(e)}"
        }, status=400)
    except Exception as e:
        return JsonResponse({
            "success": False,
            "message": f"请求处理失败: {str(e)}"
        }, status=500)

@csrf_exempt
def get_latest_data_api(request):
    """获取最新采集数据接口"""
    try:
        data = json.loads(request.body.decode("utf8"))
        ip = data.get("ip")
        port = int(data.get("port"))
        
        logger.info(f"获取最新数据请求: IP={ip}, Port={port}")
        
        # 获取最新的CPU数据
        latest_cpu = CPUPerformanceMetrics.objects.filter(
            ipaddress=ip
        ).order_by('-currentTime').first()
        
        # 获取最新的内存数据
        latest_memory = MemoryPerformanceMetrics.objects.filter(
            ipaddress=ip
        ).order_by('-currentTime').first()
        
        # 获取最新的磁盘数据
        latest_disk = DiskPerformanceMetrics.objects.filter(
            ipaddress=ip
        ).order_by('-currentTime').first()
        
        # 获取最新的网络数据
        latest_network = NetworkPerformanceMetrics.objects.filter(
            ipaddress=ip
        ).order_by('-currentTime').first()
        
        # 检查是否有任何数据
        has_data = any([latest_cpu, latest_memory, latest_disk, latest_network])
        
        if not has_data:
            logger.warning(f"IP {ip} 没有找到任何性能数据")
            return JsonResponse({
                "success": True,
                "data": {
                    "cpu": {"message": f"IP {ip} 暂无CPU数据，请先采集数据"},
                    "memory": {"message": f"IP {ip} 暂无内存数据，请先采集数据"},
                    "disk": {"message": f"IP {ip} 暂无磁盘数据，请先采集数据"},
                    "network": {"message": f"IP {ip} 暂无网络数据，请先采集数据"}
                },
                "message": f"IP {ip} 暂无数据，请先通过其他页面采集数据"
            })
        
        # 转换数据格式
        def convert_cpu_data(cpu_obj):
            if not cpu_obj:
                return {"message": f"IP {ip} 暂无CPU数据"}
            return {
                'cpu_percent': float(cpu_obj.percent),
                'cpu_count': cpu_obj.count,
                'cpu_user_time': cpu_obj.userTime,
                'cpu_system_time': cpu_obj.SystemTime,
                'cpu_idle_time': cpu_obj.Idle,
                'cpu_wait_time': cpu_obj.waitIO,
                'host': ip,
                'time': cpu_obj.currentTime.strftime('%Y-%m-%d %H:%M:%S')
            }
        
        def convert_memory_data(mem_obj):
            if not mem_obj:
                return {"message": f"IP {ip} 暂无内存数据"}
            return {
                'mem_percent': float(mem_obj.percent),
                'mem_total': mem_obj.total,
                'mem_used': mem_obj.used,
                'mem_free': mem_obj.free,
                'mem_buffers': mem_obj.buffers,
                'mem_cached': mem_obj.cache,
                'swap_used': mem_obj.swap,
                'swap_total': mem_obj.swap,  # 简化处理
                'time': mem_obj.currentTime.strftime('%Y-%m-%d %H:%M:%S')
            }
        
        def convert_disk_data(disk_obj):
            if not disk_obj:
                return {"message": f"IP {ip} 暂无磁盘数据"}
            return {
                'disk_percent': float(disk_obj.percent),
                'disk_total': disk_obj.total,
                'disk_used': disk_obj.used,
                'disk_free': disk_obj.free,
                'disk_read': disk_obj.readBytes,
                'disk_write': disk_obj.writeBytes,
                'time': disk_obj.currentTime.strftime('%Y-%m-%d %H:%M:%S')
            }
        
        def convert_network_data(net_obj):
            if not net_obj:
                return {"message": f"IP {ip} 暂无网络数据"}
            return {
                'net_bytes_sent': net_obj.sent,
                'net_bytes_recv': net_obj.recv,
                'net_packets_sent': net_obj.packetSent,
                'net_packets_recv': net_obj.packetRecv,
                'host': ip,
                'time': net_obj.currentTime.strftime('%Y-%m-%d %H:%M:%S')
            }
        
        response_data = {
            "cpu": convert_cpu_data(latest_cpu),
            "memory": convert_memory_data(latest_memory),
            "disk": convert_disk_data(latest_disk),
            "network": convert_network_data(latest_network)
        }
        
        logger.info(f"返回数据: CPU={'有数据' if latest_cpu else '无数据'}, "
                   f"内存={'有数据' if latest_memory else '无数据'}, "
                   f"磁盘={'有数据' if latest_disk else '无数据'}, "
                   f"网络={'有数据' if latest_network else '无数据'}")
        
        return JsonResponse({
            "success": True,
            "data": response_data
        })
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON解析失败: {e}")
        return JsonResponse({
            "success": False,
            "message": f"JSON解析失败: {str(e)}"
        }, status=400)
    except Exception as e:
        logger.error(f"获取最新数据失败: {e}")
        return JsonResponse({
            "success": False,
            "message": f"获取数据失败: {str(e)}"
        }, status=500)

@csrf_exempt
def get_latest_data(request):
    """获取最新采集数据接口（简化版，不需要IP参数）"""
    try:
        # 获取最新的CPU数据
        latest_cpu = CPUPerformanceMetrics.objects.all().order_by('-currentTime').first()
        logger.info(f"CPU数据查询结果: {'找到' if latest_cpu else '未找到'}")
        
        # 获取最新的内存数据
        latest_memory = MemoryPerformanceMetrics.objects.all().order_by('-currentTime').first()
        logger.info(f"内存数据查询结果: {'找到' if latest_memory else '未找到'}")
        
        # 获取最新的磁盘数据
        latest_disk = DiskPerformanceMetrics.objects.all().order_by('-currentTime').first()
        logger.info(f"磁盘数据查询结果: {'找到' if latest_disk else '未找到'}")
        
        # 获取最新的网络数据
        latest_network = NetworkPerformanceMetrics.objects.all().order_by('-currentTime').first()
        logger.info(f"网络数据查询结果: {'找到' if latest_network else '未找到'}")
        
        # 准备返回数据
        response_data = {
            "cpu_usage": 0,
            "memory_usage": 0,
            "disk_usage": 0,
            "network_usage": 0
        }
        
        # 更新CPU使用率
        if latest_cpu:
            response_data["cpu_usage"] = float(latest_cpu.percent)
            logger.info(f"CPU使用率: {response_data['cpu_usage']}%")
        
        # 更新内存使用率
        if latest_memory:
            response_data["memory_usage"] = float(latest_memory.percent)
            logger.info(f"内存使用率: {response_data['memory_usage']}%")
        
        # 更新磁盘使用率
        if latest_disk:
            response_data["disk_usage"] = float(latest_disk.percent)
            logger.info(f"磁盘使用率: {response_data['disk_usage']}%")
        
        # 更新网络性能（基于网络流量计算）
        if latest_network:
            try:
                # 计算网络使用率（基于发送和接收的字节数）
                sent_bytes = float(latest_network.sent) if latest_network.sent else 0
                recv_bytes = float(latest_network.recv) if latest_network.recv else 0
                total_bytes = sent_bytes + recv_bytes
                
                # 将字节数转换为0-1之间的使用率（假设1GB为满负荷）
                network_usage = min(1.0, total_bytes / (1024 * 1024 * 1024))
                response_data["network_usage"] = network_usage
                logger.info(f"网络使用率: {network_usage:.2%}")
            except (ValueError, TypeError) as e:
                logger.warning(f"网络数据转换失败: {e}")
                response_data["network_usage"] = 0.0
        
        return JsonResponse({
            "success": True,
            "data": response_data
        })
        
    except Exception as e:
        logger.error(f"获取最新数据失败: {str(e)}")
        return JsonResponse({
            "success": False,
            "message": f"获取数据失败: {str(e)}"
        }, status=500)

@csrf_exempt
def save_collected_data_api(request):
    """保存采集数据接口"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST allowed'}, status=405)

    try:
        data = json.loads(request.body.decode("utf8"))
        logger.info(f"收到保存数据请求: {data}")

        # 获取数据类型和IP地址 - 支持多种字段名
        data_type = data.get('type', 'unknown')
        ip_address = data.get('host', data.get('ip', data.get('ipaddress', '')))

        # 如果没有IP地址，尝试从info字段中获取
        if not ip_address and 'info' in data:
            info = data['info']
            if isinstance(info, dict):
                ip_address = info.get('host', info.get('ip', info.get('ipaddress', '')))

        if not ip_address:
            logger.warning(f"缺少IP地址信息，数据: {data}")
            return JsonResponse({
                'success': False,
                'message': '缺少IP地址信息'
            }, status=400)

        # 提取实际的数据内容
        actual_data = data
        if 'info' in data and isinstance(data['info'], dict):
            actual_data = data['info']

        logger.info(f"处理数据: IP={ip_address}, 类型={data_type}, 数据={actual_data}")

        # 根据数据类型保存到对应的表
        if 'cpu' in data_type.lower() or 'cpu_percent' in actual_data:
            # 保存CPU数据
            cpu_data = CPUPerformanceMetrics(
                type='cpu',
                ipaddress=ip_address,
                percent=actual_data.get('cpu_percent', 0),
                count=actual_data.get('cpu_count', 0),
                userTime=actual_data.get('cpu_user', actual_data.get('cpu_user_time', 0)),
                SystemTime=actual_data.get('cpu_system', actual_data.get('cpu_system_time', 0)),
                Idle=actual_data.get('cpu_idle', actual_data.get('cpu_idle_time', 0)),
                waitIO=actual_data.get('cpu_iowait', actual_data.get('cpu_wait_time', 0)),
                currentTime=django_timezone.now()
            )
            cpu_data.save()
            logger.info(f"保存CPU数据成功: {cpu_data.id}")

        elif 'memory' in data_type.lower() or 'mem_percent' in actual_data:
            # 保存内存数据
            memory_data = MemoryPerformanceMetrics(
                type='memory',
                ipaddress=ip_address,
                percent=actual_data.get('mem_percent', 0),
                total=actual_data.get('mem_total', ''),
                used=actual_data.get('mem_used', ''),
                free=actual_data.get('mem_free', ''),
                buffers=actual_data.get('mem_buffers', ''),
                cache=actual_data.get('mem_cached', ''),
                swap=actual_data.get('swap_used', ''),
                currentTime=django_timezone.now()
            )
            memory_data.save()
            logger.info(f"保存内存数据成功: {memory_data.id}")

        elif 'disk' in data_type.lower() or 'disk_usage' in actual_data:
            # 保存磁盘数据
            disk_data = DiskPerformanceMetrics(
                type='disk',
                ipaddress=ip_address,
                total=actual_data.get('disk_total', ''),
                used=actual_data.get('disk_used', ''),
                free=actual_data.get('disk_free', ''),
                percent=actual_data.get('disk_percent', 0),
                readCount=actual_data.get('disk_read_count', 0),
                writeCount=actual_data.get('disk_write_count', 0),
                readBytes=actual_data.get('disk_read_bytes', 0),
                writeBytes=actual_data.get('disk_write_bytes', 0),
                currentTime=django_timezone.now()
            )
            disk_data.save()
            logger.info(f"保存磁盘数据成功: {disk_data.id}")

        elif 'network' in data_type.lower() or 'net_bytes_sent' in actual_data:
            # 保存网络数据
            network_data = NetworkPerformanceMetrics(
                type='network',
                ipaddress=ip_address,
                sent=actual_data.get('net_bytes_sent', ''),
                recv=actual_data.get('net_bytes_recv', ''),
                packetSent=actual_data.get('net_packets_sent', ''),
                packetRecv=actual_data.get('net_packets_recv', ''),
                currentTime=django_timezone.now()
            )
            network_data.save()
            logger.info(f"保存网络数据成功: {network_data.id}")
        else:
            # 通用数据保存，尝试自动识别
            # 如果包含CPU相关字段，保存为CPU数据
            if any(key in actual_data for key in ['cpu_percent', 'cpu_user', 'cpu_system']):
                cpu_data = CPUPerformanceMetrics(
                    type='cpu',
                    ipaddress=ip_address,
                    percent=actual_data.get('cpu_percent', 0),
                    count=actual_data.get('cpu_count', 0),
                    userTime=actual_data.get('cpu_user', 0),
                    SystemTime=actual_data.get('cpu_system', 0),
                    Idle=actual_data.get('cpu_idle', 0),
                    waitIO=actual_data.get('cpu_iowait', 0),
                    currentTime=django_timezone.now()
                )
                cpu_data.save()
                logger.info(f"自动识别并保存CPU数据成功: {cpu_data.id}")
            else:
                logger.warning(f"无法识别数据类型，跳过保存: {actual_data}")

        return JsonResponse({
            'success': True,
            'message': '数据保存成功'
        })

    except json.JSONDecodeError as e:
        logger.error(f"JSON解析失败: {e}")
        return JsonResponse({
            'success': False,
            'message': f'JSON解析失败: {str(e)}'
        }, status=400)
    except Exception as e:
        logger.error(f"保存采集数据失败: {e}")
        return JsonResponse({
            'success': False,
            'message': f'数据保存失败: {str(e)}'
        }, status=500)

@csrf_exempt
def upload_log(request):
    """
    上传日志文件（文件本体存入数据库）
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': '只支持POST请求'}, status=405)
    
    try:
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        log_type = request.POST.get('type', 'system')
        
        if not title:
            return JsonResponse({'status': 'error', 'message': '日志标题不能为空'}, status=400)
        
        files = []
        for key in request.FILES:
            log_file = request.FILES[key]
            original_name = log_file.name
            size = log_file.size
            # 读取全部字节到内存（日志通常不大；若需要可改为分块累积）
            file_bytes = b''.join(chunk for chunk in log_file.chunks())
            
            log_record = LogRecord(
                title=title,
                description=description,
                type=log_type,
                original_name=original_name,
                file_blob=file_bytes,
                size=size,
                status='success'
            )
            log_record.save()
            
            files.append({
                'id': log_record.id,
                'name': original_name,
                'size': size
            })
        
        return JsonResponse({
            'status': 'success',
            'message': '日志上传成功',
            'files': files
        })
    except Exception as e:
        logging.error(f"日志上传失败: {str(e)}")
        return JsonResponse({'status': 'error', 'message': f'日志上传失败: {str(e)}'}, status=500)

@csrf_exempt
def get_logs(request):
    """
    获取所有日志记录
    """
    try:
        logs = LogRecord.objects.all()
        log_list = []
        
        for log in logs:
            log_list.append({
                'id': log.id,
                'title': log.title,
                'description': log.description,
                'type': log.type,
                'size': log.size,
                'status': log.status,
                'created_at': log.created_at.isoformat(),
                'updated_at': log.updated_at.isoformat()
            })
        
        return JsonResponse({
            'status': 'success',
            'logs': log_list
        })
    except Exception as e:
        logging.error(f"获取日志记录失败: {str(e)}")
        return JsonResponse({'status': 'error', 'message': f'获取日志记录失败: {str(e)}'}, status=500)

@csrf_exempt
def view_log(request, log_id):
    """
    查看日志内容（优先从数据库读取）
    """
    try:
        log = LogRecord.objects.get(id=log_id)
        # 如果数据库里有文件内容，按文本尝试解码
        if log.file_blob:
            try:
                content = log.file_blob.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    content = log.file_blob.decode('gbk')
                except UnicodeDecodeError:
                    return JsonResponse({
                        'status': 'success',
                        'is_binary': True,
                        'message': '此文件可能是二进制格式或使用了不支持的编码，无法直接显示内容。请使用下载功能后在本地查看。',
                        'log': {
                            'id': log.id,
                            'title': log.title,
                            'type': log.type,
                            'created_at': log.created_at.isoformat()
                        }
                    })
            return JsonResponse({
                'status': 'success',
                'is_binary': False,
                'content': content,
                'log': {
                    'id': log.id,
                    'title': log.title,
                    'type': log.type,
                    'created_at': log.created_at.isoformat()
                }
            })
        
        # 兼容旧数据：走文件路径
        file_name = os.path.basename(log.file_path or '')
        file_ext = os.path.splitext(file_name)[1].lower()
        binary_formats = ['.doc', '.docx', '.pdf', '.xls', '.xlsx', '.ppt', '.pptx', '.zip', '.rar', '.tar', '.gz', '.7z', '.exe', '.dll']
        if file_ext in binary_formats:
            return JsonResponse({
                'status': 'success',
                'is_binary': True,
                'message': f'这是一个{file_ext}格式的二进制文件，无法直接显示内容。请使用下载功能后在本地查看。',
                'file_type': file_ext,
                'log': {
                    'id': log.id,
                    'title': log.title,
                    'type': log.type,
                    'created_at': log.created_at.isoformat()
                }
            })
        try:
            with open(log.file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            try:
                with open(log.file_path, 'r', encoding='gbk') as f:
                    content = f.read()
            except UnicodeDecodeError:
                return JsonResponse({
                    'status': 'success',
                    'is_binary': True,
                    'message': '此文件可能是二进制格式或使用了不支持的编码，无法直接显示内容。请使用下载功能后在本地查看。',
                    'log': {
                        'id': log.id,
                        'title': log.title,
                        'type': log.type,
                        'created_at': log.created_at.isoformat()
                    }
                })
        return JsonResponse({
            'status': 'success',
            'is_binary': False,
            'content': content,
            'log': {
                'id': log.id,
                'title': log.title,
                'type': log.type,
                'created_at': log.created_at.isoformat()
            }
        })
    except LogRecord.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '日志记录不存在'}, status=404)
    except Exception as e:
        logging.error(f"查看日志内容失败: {str(e)}")
        return JsonResponse({'status': 'error', 'message': f'查看日志内容失败: {str(e)}'}, status=500)

@csrf_exempt
def download_log(request, log_id):
    """
    下载日志文件（优先从数据库读取）
    """
    try:
        log = LogRecord.objects.get(id=log_id)
        filename = log.original_name or (os.path.basename(log.file_path) if log.file_path else f'log_{log.id}.log')
        if log.file_blob:
            response = HttpResponse(bytes(log.file_blob), content_type='application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        # 兼容旧数据：走文件路径
        if not log.file_path or not os.path.exists(log.file_path):
            return JsonResponse({'status': 'error', 'message': '日志文件不存在'}, status=404)
        with open(log.file_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except LogRecord.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '日志记录不存在'}, status=404)
    except Exception as e:
        logging.error(f"下载日志文件失败: {str(e)}")
        return JsonResponse({'status': 'error', 'message': f'下载日志文件失败: {str(e)}'}, status=500)

@csrf_exempt
def delete_log(request, log_id):
    """
    删除日志记录
    """
    if request.method != 'DELETE':
        return JsonResponse({'status': 'error', 'message': '只支持DELETE请求'}, status=405)
    
    try:
        log = LogRecord.objects.get(id=log_id)
        
        # 删除文件（仅当存在有效文件路径时）
        if getattr(log, 'file_path', None):
            try:
                if os.path.exists(log.file_path):
                    os.remove(log.file_path)
            except Exception as file_err:
                logging.warning(f"删除日志文件失败（忽略并继续删除记录）: {file_err}")
        
        # 删除记录
        log.delete()
        
        return JsonResponse({
            'status': 'success',
            'message': '日志记录删除成功'
        })
    except LogRecord.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '日志记录不存在'}, status=404)
    except Exception as e:
        logging.error(f"删除日志记录失败: {str(e)}")
        return JsonResponse({'status': 'error', 'message': f'删除日志记录失败: {str(e)}'}, status=500)

@csrf_exempt
def create_direct_log(request):
    """
    直接在网页上创建日志
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': '只支持POST请求'}, status=405)
    
    try:
        title = request.POST.get('title')
        content = request.POST.get('content')
        log_type = request.POST.get('type', 'system')
        
        if not title:
            return JsonResponse({'status': 'error', 'message': '日志标题不能为空'}, status=400)
        
        if not content:
            return JsonResponse({'status': 'error', 'message': '日志内容不能为空'}, status=400)
        
        # 确保日志存储目录存在
        log_dir = os.path.join(settings.BASE_DIR, 'uploads', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        # 生成唯一文件名
        file_name = f"{uuid.uuid4()}_direct_{title}.txt"
        file_path = os.path.join(log_dir, file_name)
        
        # 将内容写入文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # 获取文件大小
        file_size = os.path.getsize(file_path)
        
        # 创建日志记录
        log_record = LogRecord(
            title=title,
            description=f"直接记录的日志 - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            type=log_type,
            file_path=file_path,
            size=file_size,
            status='success'
        )
        log_record.save()
        
        return JsonResponse({
            'status': 'success',
            'message': '日志记录成功',
            'log': {
                'id': log_record.id,
                'title': log_record.title,
                'type': log_record.type,
                'size': log_record.size
            }
        })
    except Exception as e:
        logging.error(f"直接记录日志失败: {str(e)}")
        return JsonResponse({'status': 'error', 'message': f'直接记录日志失败: {str(e)}'}, status=500)

