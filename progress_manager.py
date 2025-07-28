"""
翻译进度管理器
负责跟踪和管理每个文件的翻译进度
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

from translate_helper.translate_helper_base import TranslateHelper


@dataclass
class FileProgress:
    """单个文件的进度信息"""
    file_path: str
    file_type: str
    total_count: int
    translated_count: int
    completed: bool = False
    description: str = ""
    translating: bool = False  # 是否正在翻译中
    no_contents: bool = False  # 是否没有内容需要翻译
    
    @property
    def progress_percentage(self) -> float:
        """获取进度百分比"""
        if self.total_count == 0:
            return 0.0
        return (self.translated_count / self.total_count) * 100
    
    @property
    def status(self) -> str:
        """获取状态描述"""
        if self.completed:
            return "已完成"
        elif self.no_contents:
            return "无可翻译内容"
        elif self.translating:
            return "翻译中"
        else:
            return "待翻译"
        
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FileProgress':
        """从字典创建FileProgress实例"""
        return cls(
            file_path=data.get('file_path', ''),
            file_type=data.get('file_type', ''),
            total_count=data.get('total_count', 0),
            translated_count=data.get('translated_count', 0),
            completed=data.get('completed', False),
            description=data.get('description', ''),
            no_contents=data.get('no_contents', False),
        )


class ProgressManager:
    """翻译进度管理器"""
    
    STATUS_IDLE = "idle"
    STATUS_RUNNING = "running"
    STATUS_INTERUPTED = "interrupted"
    
    def __init__(self, config: Dict[str, Any], mod_work_dir: Path, logger: logging.Logger):
        """
        初始化进度管理器
        
        Args:
            config: 翻译配置
            mod_work_dir: 模组工作目录
            logger: 日志记录器
        """
        self.config = config
        self.mod_work_dir = mod_work_dir
        self.logger = logger
        self.status = "idle" # idle running
        self.current_translated_file = ""
        self.total_files = 0
        self.completed_files = 0
        
        # 文件进度缓存
        self._file_progress_cache: Dict[str, FileProgress] = {}
        
        # 进度文件路径
        self.progress_file = self.mod_work_dir / "translation_progress.json"
        
        # 初始化进度信息
        self._initialize_progress()
        
        # 从现有临时文件同步进度
        self.sync_progress_from_temp_files()
        
    def set_translated_status(self, status: str, file_path: str = ""):
        """
        设置当前翻译状态
        
        Args:
            status: 状态字符串
            file_path: 当前翻译的文件路径
        """
        if status == self.STATUS_IDLE:
            if self.current_translated_file != "":
                self._file_progress_cache[self.current_translated_file].translating = False
        if status == self.STATUS_INTERUPTED:
            if self.current_translated_file != "":
                self._file_progress_cache[self.current_translated_file].translating = False        
        
        self.status = status
        self.current_translated_file = file_path
        if self.status == self.STATUS_RUNNING and file_path:
            if file_path in self._file_progress_cache:
                self._file_progress_cache[file_path].translating = True
        
        self.logger.info(f"设置翻译状态: {status}, 当前文件: {file_path}")
    
    def is_interrupted(self) -> bool:
        return self.status == self.STATUS_INTERUPTED
        
    def refresh_files_status(self):
        self.total_files = 0
        self.completed_files = 0
        for progress in self._file_progress_cache.values():
            if progress.completed:
                self.completed_files += 1
            self.total_files += 1
    
    def _initialize_progress(self):
        """初始化所有文件的进度信息"""
        self.logger.info("初始化翻译进度管理器")
        
        # 获取所有配置的文件
        all_files_config = {}
        all_files_config.update(self.config.get("csv_files", {}))
        all_files_config.update(self.config.get("json_files", {}))
        all_files_config.update(self.config.get("jar_files", {}))
        
        # 载入文件记录
        
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    j_data = json.load(f)
                    for path, data in j_data.items():
                        file_type = TranslateHelper.get_file_type(path, self.config)
                        if file_type == "unknown":
                            self.logger.warning(f"跳过未知文件类型(可能是后来删除的文件): {path}")
                            continue
                        self._file_progress_cache[path] = FileProgress.from_dict(data)
            except Exception as e:
                self.logger.error(f"加载进度文件失败: {e}")
        
        for file_path, file_config in all_files_config.items():
            # 确定文件类型
            file_type = TranslateHelper.get_file_type(file_path, self.config)
            
            # 获取文件描述
            description = self._get_file_description(file_path, file_type, file_config)
            
            total_count = 0
            
            if file_path in self._file_progress_cache:
                total_count = self._file_progress_cache[file_path].total_count
            
            # 计算已翻译数量
            translated_count = self._count_translated_objects(file_path)
            
            # 判断是否完成
            completed = total_count > 0 and translated_count >= total_count
            
            # 创建进度对象
            progress = FileProgress(
                file_path=file_path,
                file_type=file_type,
                total_count=total_count,
                translated_count=translated_count,
                completed=completed,
                description=description
            )
            
            self._file_progress_cache[file_path] = progress
            
            self.logger.debug(f"初始化文件进度: {file_path} - {translated_count}/{total_count}")
            self.total_files += 1
            self.completed_files += (1 if completed else 0)
    
    
    def _get_file_description(self, file_path: str, file_type: str, file_config: Any) -> str:
        """获取文件描述"""
        if file_type == "csv":
            return f"CSV文件"
        elif file_type == "json":
            if isinstance(file_config, dict):
                return file_config.get("description", "JSON文件")
            return "JSON文件"
        elif file_type == "jar":
            if isinstance(file_config, dict):
                return file_config.get("description", "JAR包文件")
            return "JAR包文件"
        else:
            return "未知文件类型"
    
    
    def _count_translated_objects(self, file_path: str) -> int:
        """计算已翻译的对象数量"""
        try:
            # 构建临时翻译文件路径
            temp_file = self.get_temp_file_path(file_path)
            
            if not temp_file.exists():
                return 0
            
            # 读取临时翻译文件计算已翻译数量
            translated_count = 0
            with open(temp_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        try:
                            # data = json.loads(line.strip())
                            # 检查是否已翻译
                            # if data.get('is_translated', False) and data.get('translation', '').strip():
                            translated_count += 1
                        except json.JSONDecodeError:
                            continue
            
            return translated_count
            
        except Exception as e:
            self.logger.warning(f"计算已翻译对象数失败 {file_path}: {e}")
            return 0
    
    def get_temp_file_path(self, file_path: str) -> Path:
        """获取临时翻译文件路径"""
        file_type = TranslateHelper.get_file_type(file_path, self.config)
        helper = TranslateHelper.get_helper_by_file_type(file_type, self.logger, self.config)
        if not helper:
            self.logger.error(f"未找到支持的翻译助手: {file_type}")
            return Path("")
        return helper.get_translated_temp_file_path(file_path)
    
    def get_org_file_path(self, file_path: str) -> Path:
        file_type = TranslateHelper.get_file_type(file_path, self.config)
        helper = TranslateHelper.get_helper_by_file_type(file_type, self.logger, self.config)
        if not helper:
            self.logger.error(f"未找到支持的翻译助手: {file_type}")
            return Path("")
        return helper.get_original_file_path(file_path)
    
    def sync_progress_from_temp_files(self):
        """
        从临时翻译文件同步进度信息
        比refresh_progress轻量，只读取临时文件的翻译数量
        """
        for file_path in self._file_progress_cache.keys():
            progress = self._file_progress_cache[file_path]
            translated_count = self._count_translated_objects(file_path)
            progress.translated_count = translated_count
            progress.completed = progress.total_count > 0 and translated_count >= progress.total_count
            
            self.logger.debug(f"同步文件进度: {file_path} - {translated_count}/{progress.total_count}")
    
    def update_translation_progress(self, file_path: str, translated_count: int):
        """
        更新翻译进度（内存操作，不涉及文件扫描）
        
        Args:
            file_path: 文件路径
            translated_count: 已翻译数量
        """
        if file_path in self._file_progress_cache:
            progress = self._file_progress_cache[file_path]
            progress.translated_count = translated_count
            progress.completed = progress.total_count > 0 and translated_count >= progress.total_count
            
            self.logger.debug(f"更新翻译进度: {file_path} - {translated_count}/{progress.total_count}")
    
    def increment_translation_progress(self, file_path: str, increment: int = 1):
        """
        增量更新翻译进度
        
        Args:
            file_path: 文件路径
            increment: 增加的翻译数量，默认为1
        """
        if file_path in self._file_progress_cache:
            progress = self._file_progress_cache[file_path]
            progress.translated_count += increment
            progress.completed = progress.total_count > 0 and progress.translated_count >= progress.total_count
            
            self.logger.debug(f"增量更新翻译进度: {file_path} - {progress.translated_count}/{progress.total_count}")
    
    def set_file_total_count(self, file_path: str, total_count: int):
        """
        设置文件的总翻译对象数量
        
        Args:
            file_path: 文件路径
            total_count: 总数量
        """
        if file_path in self._file_progress_cache:
            progress = self._file_progress_cache[file_path]
            progress.total_count = total_count
            progress.completed = total_count > 0 and progress.translated_count >= total_count
            
            self.logger.debug(f"设置文件总数量: {file_path} - {progress.translated_count}/{total_count}")
            self.save_progress()
            
    def save_progress(self):
        """保存当前进度到文件"""
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump({path: asdict(progress) for path, progress in self._file_progress_cache.items()}, f, ensure_ascii=False, indent=4)
            self.logger.info(f"已保存进度到文件: {self.progress_file}")
        except Exception as e:
            self.logger.error(f"保存进度文件失败: {e}")
    
    def get_file_progress(self, file_path: str) -> Optional[FileProgress]:
        """获取单个文件的进度"""
        return self._file_progress_cache.get(file_path)
    
    def get_all_progress(self) -> Dict[str, FileProgress]:
        """获取所有文件的进度"""
        return self._file_progress_cache.copy()
    
    def get_overall_progress(self) -> Dict[str, Any]:
        """获取总体进度统计"""
        total_files = len(self._file_progress_cache)
        completed_files = sum(1 for p in self._file_progress_cache.values() if p.completed)
        
        return {
            "total_files": total_files,
            "completed_files": completed_files,
            "files_percentage": (completed_files / total_files * 100) if total_files > 0 else 0.0
        }
    
    def reset_progress(self, file_path: Optional[str] = None):
        """
        重置进度
        
        Args:
            file_path: 指定文件路径，如果为None则重置所有文件
        """
        if file_path:
            # 重置单个文件
            if file_path in self._file_progress_cache:
                progress = self._file_progress_cache[file_path]
                progress.translated_count = 0
                progress.completed = False
                
                # 删除临时翻译文件
                temp_file = self.get_temp_file_path(file_path)
                if temp_file.exists():
                    try:
                        temp_file.unlink()
                        self.logger.info(f"删除临时翻译文件: {temp_file}")
                    except Exception as e:
                        self.logger.error(f"删除临时翻译文件失败: {e}")
                # 删除源文件, 确保下次开始翻译是最新的文件
                org_file = self.get_org_file_path(file_path)
                try:
                    org_file.unlink()
                    self.logger.info(f"删除源文件: {org_file}")
                except Exception as e:
                    self.logger.error(f"删除源文件失败: {e}")
                
                self.logger.info(f"重置文件进度: {file_path}")
        else:
            # 重置所有文件
            for fp in list(self._file_progress_cache.keys()):
                self.reset_progress(fp)
