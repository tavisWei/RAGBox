#!/bin/bash
# RAG Platform 一键部署脚本
# 支持低/中/高三种资源配置部署

set -e

VERSION="1.0.0"
DATA_DIR="./data"
COMPOSE_PROJECT_NAME="rag-platform"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "检查前置条件..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装，请先安装 Docker: https://docs.docker.com/get-docker/"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose 未安装"
        exit 1
    fi
    
    log_info "前置条件检查通过"
}

select_mode() {
    echo ""
    echo "请选择部署模式："
    echo "1) 低资源配置 (SQLite) - 4GB RAM, <1万文档"
    echo "2) 中资源配置 (PostgreSQL + pgvector) - 8GB RAM, 1-100万文档"
    echo "3) 高资源配置 (Elasticsearch) - 16GB+ RAM, >100万文档"
    echo ""
    read -p "请输入选项 [1]: " mode
    
    case $mode in
        1|"") 
            export PROFILE="low"
            log_info "已选择: 低资源配置"
            ;;
        2) 
            export PROFILE="medium"
            log_info "已选择: 中资源配置"
            ;;
        3) 
            export PROFILE="high"
            log_info "已选择: 高资源配置"
            ;;
        *) 
            log_error "无效选项，使用默认配置"
            export PROFILE="low"
            ;;
    esac
}

create_data_dir() {
    log_info "创建数据目录..."
    mkdir -p "$DATA_DIR"
    mkdir -p "$DATA_DIR/uploads"
    chmod -R 755 "$DATA_DIR"
}

pull_images() {
    log_info "拉取 Docker 镜像..."
    if docker compose version &> /dev/null; then
        docker compose -f docker-compose.yml -f "docker-compose.$PROFILE.yml" pull
    else
        docker-compose -f docker-compose.yml -f "docker-compose.$PROFILE.yml" pull
    fi
}

start_services() {
    log_info "启动服务..."
    
    if docker compose version &> /dev/null; then
        docker compose -f docker-compose.yml -f "docker-compose.$PROFILE.yml" up -d
    else
        docker-compose -f docker-compose.yml -f "docker-compose.$PROFILE.yml" up -d
    fi
    
    log_info "等待服务就绪..."
    sleep 15
    
    check_services
}

check_services() {
    log_info "检查服务状态..."
    
    if curl -sf http://localhost:5001/api/v1/health > /dev/null 2>&1; then
        log_info "API 服务: ${GREEN}健康${NC}"
    else
        log_warn "API 服务: ${RED}未就绪${NC}"
    fi
    
    if curl -sf http://localhost:3000 > /dev/null 2>&1; then
        log_info "Web 服务: ${GREEN}健康${NC}"
    else
        log_warn "Web 服务: ${RED}未就绪${NC}"
    fi
}

show_status() {
    echo ""
    echo "========================================"
    echo "  RAG Platform 部署完成!"
    echo "========================================"
    echo ""
    echo "访问地址:"
    echo "  Web 界面:    http://localhost:3000"
    echo "  API 服务:    http://localhost:5001"
    echo "  API 文档:    http://localhost:5001/docs"
    echo ""
    echo "默认账号:"
    echo "  邮箱:    admin@example.com"
    echo "  密码:    admin123"
    echo ""
    echo "查看日志:"
    echo "  docker compose logs -f api"
    echo "  docker compose logs -f web"
    echo ""
    echo "停止服务:"
    echo "  docker compose down"
    echo ""
}

main() {
    echo "========================================"
    echo "  RAG Platform 部署脚本 v${VERSION}"
    echo "========================================"
    
    check_prerequisites
    select_mode
    create_data_dir
    pull_images
    start_services
    show_status
    
    log_info "部署完成!"
}

main "$@"