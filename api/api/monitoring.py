from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import time
import os
from .deps import get_current_user

router = APIRouter()

_request_count = 0
_error_count = 0
_total_response_time = 0.0
_start_time = time.time()


class StatsResponse(BaseModel):
    total_queries: int
    total_knowledge_bases: int
    total_documents: int
    avg_response_time_ms: float


class SystemMetricsResponse(BaseModel):
    cpu_percent: float
    cpu_count: int
    memory_total_gb: float
    memory_used_gb: float
    memory_percent: float
    disk_total_gb: float
    disk_used_gb: float
    disk_percent: float
    network_sent_mb: float
    network_recv_mb: float
    boot_time: int
    uptime_seconds: int


class PlatformMetricsResponse(BaseModel):
    uptime_seconds: int
    request_count: int
    error_count: int
    avg_response_time_ms: float
    python_version: str
    platform: str


@router.get("/monitoring/stats", response_model=StatsResponse)
async def get_stats(user: dict = Depends(get_current_user)):
    return StatsResponse(
        total_queries=0,
        total_knowledge_bases=0,
        total_documents=0,
        avg_response_time_ms=0.0,
    )


@router.get("/monitoring/system", response_model=SystemMetricsResponse)
async def get_system_metrics(user: dict = Depends(get_current_user)):
    try:
        import psutil

        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        net = psutil.net_io_counters()
        boot = psutil.boot_time()

        return SystemMetricsResponse(
            cpu_percent=psutil.cpu_percent(interval=0.1),
            cpu_count=psutil.cpu_count(),
            memory_total_gb=round(mem.total / (1024**3), 2),
            memory_used_gb=round(mem.used / (1024**3), 2),
            memory_percent=mem.percent,
            disk_total_gb=round(disk.total / (1024**3), 2),
            disk_used_gb=round(disk.used / (1024**3), 2),
            disk_percent=disk.percent,
            network_sent_mb=round(net.bytes_sent / (1024**2), 2),
            network_recv_mb=round(net.bytes_recv / (1024**2), 2),
            boot_time=int(boot),
            uptime_seconds=int(time.time() - boot),
        )
    except ImportError:
        return SystemMetricsResponse(
            cpu_percent=0,
            cpu_count=0,
            memory_total_gb=0,
            memory_used_gb=0,
            memory_percent=0,
            disk_total_gb=0,
            disk_used_gb=0,
            disk_percent=0,
            network_sent_mb=0,
            network_recv_mb=0,
            boot_time=0,
            uptime_seconds=0,
        )


@router.get("/monitoring/platform", response_model=PlatformMetricsResponse)
async def get_platform_metrics(user: dict = Depends(get_current_user)):
    global _request_count, _error_count, _total_response_time

    avg_response = 0.0
    if _request_count > 0:
        avg_response = round(_total_response_time / _request_count, 2)

    return PlatformMetricsResponse(
        uptime_seconds=int(time.time() - _start_time),
        request_count=_request_count,
        error_count=_error_count,
        avg_response_time_ms=avg_response,
        python_version=f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",
        platform=os.sys.platform,
    )


class QueryLogOut(BaseModel):
    id: str
    query: str
    knowledge_base_id: str
    response_time_ms: float
    created_at: str


@router.get("/monitoring/query-logs", response_model=List[QueryLogOut])
async def list_query_logs(user: dict = Depends(get_current_user)):
    return []


@router.get("/monitoring/processes")
async def get_processes(user: dict = Depends(get_current_user)):
    try:
        import psutil

        processes = []
        for proc in psutil.process_iter(
            ["pid", "name", "cpu_percent", "memory_percent", "status"]
        ):
            try:
                info = proc.info
                cpu = info.get("cpu_percent") or 0
                mem = info.get("memory_percent") or 0
                if cpu > 0.1 or mem > 0.1:
                    processes.append(
                        {
                            "pid": info["pid"],
                            "name": info["name"],
                            "cpu_percent": round(cpu, 1),
                            "memory_percent": round(mem, 1),
                            "status": info.get("status", "unknown"),
                        }
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        processes.sort(key=lambda x: x["cpu_percent"], reverse=True)
        return {"processes": processes[:20]}
    except ImportError:
        return {"processes": []}
