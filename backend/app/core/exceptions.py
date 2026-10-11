"""业务异常体系。

禁止裸 `Exception`：所有可预期的业务失败都必须使用这里的类型。
每个异常携带 `code`（API 响应码）、HTTP 状态码和可选的详细信息。
"""

from __future__ import annotations

from typing import Any

# ---- 错误码区间 ----
# 400xx 通用校验
# 401xx 认证/授权
# 410xx SKU / 批次
# 411xx 标题
# 412xx 图片
# 413xx QA
# 414xx 生产保护
# 415xx READY
# 416xx 产品类型 / 配置
# 500xx 系统


class AppError(Exception):
    """所有业务异常的基类。"""

    code: int = 50000
    http_status: int = 400
    default_message: str = "操作失败"

    def __init__(
        self,
        message: str | None = None,
        *,
        detail: Any = None,
        code: int | None = None,
    ) -> None:
        # 未显式给出 message 时，用字符串型 detail 兜底，避免响应体里只剩笼统的默认文案
        if message is None and isinstance(detail, str) and detail:
            message = detail
        self.message = message or self.default_message
        self.detail = detail
        if code is not None:
            self.code = code
        super().__init__(self.message)


# ---------------- 通用校验 ----------------
class ValidationError(AppError):
    code = 40001
    default_message = "校验失败"


class NotFoundError(AppError):
    code = 40004
    http_status = 404
    default_message = "资源不存在"


class ConflictError(AppError):
    code = 40009
    http_status = 409
    default_message = "资源冲突"


class IdempotencyReplay(AppError):
    code = 40010
    http_status = 200
    default_message = "请求已处理，返回首次结果"


class IdempotencyConflictError(AppError):
    """同一 operation_key 携带了不同请求内容 —— 属于非法重放，必须拒绝。"""

    code = 40011
    http_status = 409
    default_message = "同一 operation_key 携带了不同请求内容"


# ---------------- 认证授权 ----------------
class UnauthorizedError(AppError):
    code = 40101
    http_status = 401
    default_message = "未认证或凭证无效"


class ForbiddenError(AppError):
    code = 40103
    http_status = 403
    default_message = "无权限执行该操作"


# ---------------- SKU / 批次 ----------------
class BatchNotFoundError(NotFoundError):
    code = 41001
    default_message = "批次不存在"


class ProductTypeNotFoundError(NotFoundError):
    code = 41002
    default_message = "产品类型不存在"


class ProductTypeDisabledError(AppError):
    code = 41003
    default_message = "产品类型已停用"


class SkuPrefixConflictError(ConflictError):
    code = 41004
    default_message = "SKU 前缀已被占用，一旦使用永久归属该产品类型"


class SkuSequenceWidthTooSmallError(ValidationError):
    code = 41005
    default_message = "流水号位数不能缩短到容纳不了当前最大值"


class RequestSnapshotMismatchError(ValidationError):
    code = 41006
    default_message = "请求快照哈希不一致，疑似被篡改"


class BatchNotPreparedError(AppError):
    code = 41007
    default_message = "批次尚未完成生产准备"


# ---------------- 标题 ----------------
class TitlePoolExhaustedError(AppError):
    code = 41101
    default_message = "可用标题池已耗尽"


class TitleReservationNotFoundError(NotFoundError):
    code = 41102
    default_message = "标题预留记录不存在"


class TitleIdentityMismatchError(ValidationError):
    code = 41103
    default_message = "标题身份与概念语义指纹不匹配"


# ---------------- 图片 ----------------
class ImageJobNotFoundError(NotFoundError):
    code = 41201
    default_message = "图片任务不存在"


class ImageAssetNotFoundError(NotFoundError):
    code = 41202
    default_message = "图片资产不存在"


class UnsupportedImageFormatError(ValidationError):
    code = 41203
    default_message = "仅支持 PNG 格式，禁止格式转换"


class ChecksumMismatchError(ValidationError):
    code = 41204
    default_message = "字节 SHA-256 与上传声明不一致"


class ImagePolicyViolationError(ValidationError):
    code = 41205
    default_message = "图片违反 Image Policy"


# ---------------- QA ----------------
class QARecordImmutableError(ConflictError):
    code = 41301
    default_message = "QA 记录为追加式，禁止修改已有记录"


class HumanReviewRejected(AppError):
    code = 41302
    default_message = "硬技术失败永远不可人工放行"


class ReviewSnapshotStaleError(ConflictError):
    code = 41303
    default_message = "页面快照已过期，请刷新后重试"


class OCRRuntimeError(AppError):
    code = 41304
    default_message = "OCR 运行时不可用"


# ---------------- 生产保护 ----------------
class ProductionPausedError(ConflictError):
    code = 41401
    http_status = 423
    default_message = "生产已暂停，无法领取新任务"


class TrialRunNotAllowedError(AppError):
    code = 41402
    default_message = "当前状态不允许开始试运行"


# ---------------- READY ----------------
class ReadyGateBlockedError(AppError):
    code = 41501
    default_message = "未满足 READY 判定条件"


class RequiredRoleMissingError(ReadyGateBlockedError):
    code = 41502
    default_message = "必需图片角色未全部通过，整套不可 READY"


class ProductDataMissingError(ReadyGateBlockedError):
    code = 41503
    default_message = "商品属性数据缺失或 QA 指纹不匹配"


# ---------------- 系统 ----------------
class StorageWriteError(AppError):
    code = 50011
    http_status = 500
    default_message = "存储写入失败"


class ResourceIntegrityError(AppError):
    code = 50012
    http_status = 500
    default_message = "业务资源文件校验失败"


class ProviderCallError(AppError):
    code = 50013
    http_status = 502
    default_message = "外部服务调用失败"
