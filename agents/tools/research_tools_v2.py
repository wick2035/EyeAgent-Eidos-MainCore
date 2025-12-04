"""
ResearchAgent 阶段二工具
统计分析、文献处理、数据可视化、研究方案设计

Created: 2025-12-04
"""
import json
import logging
import io
import base64
from typing import Optional, Dict, Any, List
from langchain.tools import tool

logger = logging.getLogger(__name__)

# 尝试导入数据分析库
try:
    import numpy as np
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    logger.warning("[ResearchToolsV2] pandas/numpy 未安装，统计分析功能受限")

try:
    from scipy import stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    logger.warning("[ResearchToolsV2] scipy 未安装，高级统计分析功能不可用")

try:
    import matplotlib
    matplotlib.use('Agg')  # 非交互式后端
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'Arial Unicode MS']
    plt.rcParams['axes.unicode_minus'] = False
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("[ResearchToolsV2] matplotlib 未安装，数据可视化功能不可用")


# ========== 统计分析工具 ==========

@tool
def statistical_analysis(
    data_json: str,
    analysis_type: str,
    variables: str = None,
    options: str = None
) -> str:
    """
    对数据进行统计分析。

    Args:
        data_json: JSON格式的数据，格式为:
            - 数组格式: [{{"age": 25, "gender": "M"}}, {{"age": 30, "gender": "F"}}, ...]
            - 或单列格式: {{"values": [1, 2, 3, 4, 5]}}
        analysis_type: 分析类型，可选值：
            - "descriptive": 描述性统计（均值、标准差、中位数、四分位数等）
            - "correlation": 相关性分析（Pearson/Spearman相关系数）
            - "ttest": t检验（独立样本或配对样本）
            - "chi_square": 卡方检验
            - "regression": 线性回归分析
            - "anova": 方差分析
            - "survival": 生存分析（Kaplan-Meier）
        variables: 分析涉及的变量名，逗号分隔。如 "age,weight" 或 "group,value"
        options: 额外选项的JSON字符串，如 {{"paired": true, "alternative": "two-sided"}}

    Returns:
        JSON格式的分析结果，包含统计量、p值、置信区间等

    使用场景：
        - 患者数据描述性统计
        - 治疗效果对比分析
        - 风险因素相关性研究
        - 临床试验数据分析
    """
    try:
        if not PANDAS_AVAILABLE:
            return json.dumps({
                "error": True,
                "message": "统计分析功能需要安装 pandas 和 numpy：pip install pandas numpy"
            }, ensure_ascii=False)

        # 解析数据
        data = json.loads(data_json)
        if isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, dict):
            if "values" in data:
                df = pd.DataFrame({"values": data["values"]})
            else:
                df = pd.DataFrame(data)
        else:
            return json.dumps({"error": True, "message": "数据格式无效"}, ensure_ascii=False)

        # 解析变量
        var_list = [v.strip() for v in variables.split(",")] if variables else list(df.columns)

        # 解析选项
        opts = json.loads(options) if options else {}

        result = {"analysis_type": analysis_type, "n_samples": len(df)}

        # 描述性统计
        if analysis_type == "descriptive":
            result["statistics"] = {}
            for var in var_list:
                if var in df.columns:
                    col = df[var]
                    if pd.api.types.is_numeric_dtype(col):
                        result["statistics"][var] = {
                            "count": int(col.count()),
                            "mean": float(col.mean()),
                            "std": float(col.std()),
                            "min": float(col.min()),
                            "q25": float(col.quantile(0.25)),
                            "median": float(col.median()),
                            "q75": float(col.quantile(0.75)),
                            "max": float(col.max()),
                            "missing": int(col.isna().sum())
                        }
                    else:
                        # 分类变量
                        value_counts = col.value_counts().to_dict()
                        result["statistics"][var] = {
                            "type": "categorical",
                            "unique_count": int(col.nunique()),
                            "value_counts": {str(k): int(v) for k, v in value_counts.items()},
                            "missing": int(col.isna().sum())
                        }

        # 相关性分析
        elif analysis_type == "correlation":
            if not SCIPY_AVAILABLE:
                return json.dumps({"error": True, "message": "相关性分析需要安装 scipy"}, ensure_ascii=False)

            if len(var_list) < 2:
                return json.dumps({"error": True, "message": "相关性分析需要至少两个变量"}, ensure_ascii=False)

            method = opts.get("method", "pearson")
            numeric_cols = [v for v in var_list if v in df.columns and pd.api.types.is_numeric_dtype(df[v])]

            if len(numeric_cols) < 2:
                return json.dumps({"error": True, "message": "需要至少两个数值型变量"}, ensure_ascii=False)

            result["correlations"] = {}
            for i, var1 in enumerate(numeric_cols):
                for var2 in numeric_cols[i+1:]:
                    x = df[var1].dropna()
                    y = df[var2].dropna()
                    # 取交集
                    common_idx = x.index.intersection(y.index)
                    x = x.loc[common_idx]
                    y = y.loc[common_idx]

                    if method == "spearman":
                        corr, p_value = stats.spearmanr(x, y)
                    else:
                        corr, p_value = stats.pearsonr(x, y)

                    result["correlations"][f"{var1}_vs_{var2}"] = {
                        "coefficient": float(corr),
                        "p_value": float(p_value),
                        "method": method,
                        "n": len(x),
                        "significant": p_value < 0.05
                    }

        # t检验
        elif analysis_type == "ttest":
            if not SCIPY_AVAILABLE:
                return json.dumps({"error": True, "message": "t检验需要安装 scipy"}, ensure_ascii=False)

            if len(var_list) < 2:
                return json.dumps({"error": True, "message": "t检验需要指定分组变量和数值变量"}, ensure_ascii=False)

            group_var = var_list[0]
            value_var = var_list[1]
            paired = opts.get("paired", False)

            if group_var not in df.columns or value_var not in df.columns:
                return json.dumps({"error": True, "message": "指定的变量不存在"}, ensure_ascii=False)

            groups = df[group_var].unique()
            if len(groups) != 2:
                return json.dumps({"error": True, "message": "t检验需要恰好两个分组"}, ensure_ascii=False)

            group1 = df[df[group_var] == groups[0]][value_var].dropna()
            group2 = df[df[group_var] == groups[1]][value_var].dropna()

            if paired:
                t_stat, p_value = stats.ttest_rel(group1, group2)
            else:
                t_stat, p_value = stats.ttest_ind(group1, group2)

            result["ttest"] = {
                "group1": {"name": str(groups[0]), "n": len(group1), "mean": float(group1.mean()), "std": float(group1.std())},
                "group2": {"name": str(groups[1]), "n": len(group2), "mean": float(group2.mean()), "std": float(group2.std())},
                "t_statistic": float(t_stat),
                "p_value": float(p_value),
                "paired": paired,
                "significant": p_value < 0.05,
                "mean_difference": float(group1.mean() - group2.mean())
            }

        # 卡方检验
        elif analysis_type == "chi_square":
            if not SCIPY_AVAILABLE:
                return json.dumps({"error": True, "message": "卡方检验需要安装 scipy"}, ensure_ascii=False)

            if len(var_list) < 2:
                return json.dumps({"error": True, "message": "卡方检验需要两个分类变量"}, ensure_ascii=False)

            var1, var2 = var_list[0], var_list[1]
            contingency_table = pd.crosstab(df[var1], df[var2])
            chi2, p_value, dof, expected = stats.chi2_contingency(contingency_table)

            result["chi_square"] = {
                "chi2_statistic": float(chi2),
                "p_value": float(p_value),
                "degrees_of_freedom": int(dof),
                "significant": p_value < 0.05,
                "contingency_table": contingency_table.to_dict()
            }

        # 线性回归
        elif analysis_type == "regression":
            if not SCIPY_AVAILABLE:
                return json.dumps({"error": True, "message": "回归分析需要安装 scipy"}, ensure_ascii=False)

            if len(var_list) < 2:
                return json.dumps({"error": True, "message": "回归分析需要自变量和因变量"}, ensure_ascii=False)

            y_var = var_list[0]  # 因变量
            x_vars = var_list[1:]  # 自变量

            # 简单线性回归
            if len(x_vars) == 1:
                x = df[x_vars[0]].dropna()
                y = df[y_var].dropna()
                common_idx = x.index.intersection(y.index)
                x = x.loc[common_idx].values
                y = y.loc[common_idx].values

                slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)

                result["regression"] = {
                    "type": "simple_linear",
                    "dependent_variable": y_var,
                    "independent_variable": x_vars[0],
                    "slope": float(slope),
                    "intercept": float(intercept),
                    "r_squared": float(r_value ** 2),
                    "r_value": float(r_value),
                    "p_value": float(p_value),
                    "std_error": float(std_err),
                    "significant": p_value < 0.05,
                    "equation": f"{y_var} = {slope:.4f} * {x_vars[0]} + {intercept:.4f}"
                }
            else:
                result["regression"] = {
                    "error": "多元回归需要 statsmodels 库，当前仅支持简单线性回归"
                }

        # 方差分析
        elif analysis_type == "anova":
            if not SCIPY_AVAILABLE:
                return json.dumps({"error": True, "message": "方差分析需要安装 scipy"}, ensure_ascii=False)

            if len(var_list) < 2:
                return json.dumps({"error": True, "message": "ANOVA需要分组变量和数值变量"}, ensure_ascii=False)

            group_var = var_list[0]
            value_var = var_list[1]

            groups = [df[df[group_var] == g][value_var].dropna().values for g in df[group_var].unique()]
            f_stat, p_value = stats.f_oneway(*groups)

            result["anova"] = {
                "f_statistic": float(f_stat),
                "p_value": float(p_value),
                "groups": [str(g) for g in df[group_var].unique()],
                "n_groups": len(groups),
                "significant": p_value < 0.05
            }

        # 生存分析（简化版）
        elif analysis_type == "survival":
            result["survival"] = {
                "message": "完整的生存分析需要 lifelines 库。当前提供基础统计。",
                "tip": "建议安装 lifelines：pip install lifelines"
            }
            if len(var_list) >= 2:
                time_var = var_list[0]
                event_var = var_list[1]
                if time_var in df.columns and event_var in df.columns:
                    result["survival"]["summary"] = {
                        "total_observations": len(df),
                        "events": int(df[event_var].sum()),
                        "censored": int(len(df) - df[event_var].sum()),
                        "median_time": float(df[time_var].median()),
                        "mean_time": float(df[time_var].mean())
                    }

        else:
            return json.dumps({
                "error": True,
                "message": f"不支持的分析类型: {analysis_type}",
                "supported_types": ["descriptive", "correlation", "ttest", "chi_square", "regression", "anova", "survival"]
            }, ensure_ascii=False)

        logger.info(f"[ResearchToolsV2] 统计分析完成: {analysis_type}")
        return json.dumps(result, ensure_ascii=False)

    except json.JSONDecodeError as e:
        return json.dumps({"error": True, "message": f"JSON解析失败: {str(e)}"}, ensure_ascii=False)
    except Exception as e:
        logger.error(f"[ResearchToolsV2] 统计分析失败: {e}", exc_info=True)
        return json.dumps({"error": True, "message": f"统计分析失败: {str(e)}"}, ensure_ascii=False)


# ========== 文献处理工具 ==========

@tool
def summarize_medical_literature(
    content: str,
    task_type: str = "summarize",
    target_language: str = "zh"
) -> str:
    """
    处理医学文献内容：摘要提取、关键信息提取、翻译。

    Args:
        content: 文献内容（标题、摘要或全文）
        task_type: 处理类型，可选值：
            - "summarize": 生成摘要（默认）
            - "extract_key_findings": 提取关键发现
            - "translate": 翻译
            - "extract_methods": 提取研究方法
            - "extract_conclusions": 提取结论
        target_language: 目标语言（translate时使用），可选 "zh"(中文)、"en"(英文)

    Returns:
        处理后的文献内容

    使用场景：
        - 快速理解英文文献
        - 提取研究关键发现
        - 准备文献综述材料

    注意：
        - 此工具不调用外部API，通过提示词引导LLM处理
        - 返回结构化的分析指导，实际分析由Agent的LLM完成
    """
    try:
        result = {
            "task_type": task_type,
            "content_length": len(content),
            "target_language": target_language
        }

        if task_type == "summarize":
            result["instruction"] = """请对以下医学文献内容生成结构化摘要：

1. **研究背景**：研究的目的和背景
2. **研究方法**：研究设计、样本量、干预措施
3. **主要结果**：关键数据和统计结果
4. **结论**：主要结论和临床意义
5. **局限性**：研究局限性（如有提及）

文献内容：
"""
            result["content_to_process"] = content[:3000]  # 限制长度

        elif task_type == "extract_key_findings":
            result["instruction"] = """请从以下医学文献中提取关键发现，格式：

**关键发现：**
1. [发现1]
2. [发现2]
3. [发现3]
...

**统计数据：**
- [重要的p值、置信区间、效应量等]

**临床意义：**
- [对临床实践的指导意义]

文献内容：
"""
            result["content_to_process"] = content[:3000]

        elif task_type == "translate":
            lang_name = "中文" if target_language == "zh" else "English"
            result["instruction"] = f"""请将以下医学文献内容翻译为{lang_name}，要求：
1. 保持医学术语的准确性
2. 保留原文的专业表达
3. 翻译流畅自然

原文：
"""
            result["content_to_process"] = content[:2000]

        elif task_type == "extract_methods":
            result["instruction"] = """请从以下医学文献中提取研究方法信息：

**研究设计：**
- 研究类型（RCT/队列研究/病例对照等）
- 研究时间范围

**研究对象：**
- 入选标准
- 排除标准
- 样本量

**干预措施：**
- 实验组干预
- 对照组干预

**结局指标：**
- 主要结局
- 次要结局

**统计方法：**
- 使用的统计分析方法

文献内容：
"""
            result["content_to_process"] = content[:3000]

        elif task_type == "extract_conclusions":
            result["instruction"] = """请从以下医学文献中提取结论：

**主要结论：**
[一句话总结主要结论]

**支持证据：**
1. [关键数据1]
2. [关键数据2]

**临床建议：**
[对临床实践的建议]

**未来研究方向：**
[作者建议的后续研究方向]

文献内容：
"""
            result["content_to_process"] = content[:3000]

        else:
            return json.dumps({
                "error": True,
                "message": f"不支持的任务类型: {task_type}",
                "supported_types": ["summarize", "extract_key_findings", "translate", "extract_methods", "extract_conclusions"]
            }, ensure_ascii=False)

        logger.info(f"[ResearchToolsV2] 文献处理准备完成: {task_type}")
        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        logger.error(f"[ResearchToolsV2] 文献处理失败: {e}", exc_info=True)
        return json.dumps({"error": True, "message": f"文献处理失败: {str(e)}"}, ensure_ascii=False)


# ========== 数据可视化工具 ==========

@tool
def generate_research_visualization(
    data_json: str,
    chart_type: str,
    title: str = "研究数据可视化",
    x_label: str = None,
    y_label: str = None,
    options: str = None
) -> str:
    """
    生成科研数据可视化图表。

    Args:
        data_json: JSON格式的数据，格式取决于图表类型：
            - 柱状图/折线图: {{"labels": ["A", "B"], "values": [10, 20]}}
            - 散点图: {{"x": [1,2,3], "y": [4,5,6]}}
            - 饼图: {{"labels": ["A", "B"], "values": [30, 70]}}
            - 箱线图: {{"groups": {{"A": [1,2,3], "B": [4,5,6]}}}}
        chart_type: 图表类型，可选值：
            - "bar": 柱状图
            - "line": 折线图
            - "scatter": 散点图
            - "pie": 饼图
            - "boxplot": 箱线图
            - "histogram": 直方图
            - "heatmap": 热力图
        title: 图表标题
        x_label: X轴标签
        y_label: Y轴标签
        options: 额外选项JSON，如 {{"color": "blue", "figsize": [10, 6]}}

    Returns:
        JSON格式结果，包含：
        - image_base64: 图片的base64编码
        - image_url: 如果Minio可用，返回存储URL
        - description: 图表描述

    使用场景：
        - 患者年龄分布可视化
        - 治疗效果对比图
        - 时间趋势分析图
        - 相关性散点图
    """
    try:
        if not MATPLOTLIB_AVAILABLE:
            return json.dumps({
                "error": True,
                "message": "数据可视化功能需要安装 matplotlib：pip install matplotlib"
            }, ensure_ascii=False)

        if not PANDAS_AVAILABLE:
            return json.dumps({
                "error": True,
                "message": "数据可视化功能需要安装 pandas：pip install pandas"
            }, ensure_ascii=False)

        # 解析数据
        data = json.loads(data_json)
        opts = json.loads(options) if options else {}

        # 图表尺寸
        figsize = opts.get("figsize", [10, 6])
        fig, ax = plt.subplots(figsize=figsize)

        # 颜色
        color = opts.get("color", None)
        colors = opts.get("colors", None)

        description = ""

        # 柱状图
        if chart_type == "bar":
            labels = data.get("labels", [])
            values = data.get("values", [])
            bars = ax.bar(labels, values, color=color or colors)
            ax.set_xlabel(x_label or "类别")
            ax.set_ylabel(y_label or "数值")
            description = f"柱状图显示了{len(labels)}个类别的数值分布"

        # 折线图
        elif chart_type == "line":
            x = data.get("x", data.get("labels", list(range(len(data.get("values", []))))))
            y = data.get("y", data.get("values", []))
            ax.plot(x, y, marker='o', color=color or 'blue')
            ax.set_xlabel(x_label or "X")
            ax.set_ylabel(y_label or "Y")
            description = f"折线图展示了{len(y)}个数据点的变化趋势"

        # 散点图
        elif chart_type == "scatter":
            x = data.get("x", [])
            y = data.get("y", [])
            ax.scatter(x, y, c=color or 'blue', alpha=0.6)
            ax.set_xlabel(x_label or "X")
            ax.set_ylabel(y_label or "Y")
            description = f"散点图展示了{len(x)}个数据点的分布关系"

        # 饼图
        elif chart_type == "pie":
            labels = data.get("labels", [])
            values = data.get("values", [])
            ax.pie(values, labels=labels, autopct='%1.1f%%', colors=colors)
            ax.axis('equal')
            description = f"饼图展示了{len(labels)}个类别的占比分布"

        # 箱线图
        elif chart_type == "boxplot":
            groups = data.get("groups", {})
            if groups:
                box_data = [groups[k] for k in groups.keys()]
                ax.boxplot(box_data, labels=list(groups.keys()))
            else:
                values = data.get("values", [])
                ax.boxplot(values)
            ax.set_xlabel(x_label or "分组")
            ax.set_ylabel(y_label or "数值")
            description = f"箱线图展示了数据的分布特征（中位数、四分位数、异常值）"

        # 直方图
        elif chart_type == "histogram":
            values = data.get("values", [])
            bins = opts.get("bins", 20)
            ax.hist(values, bins=bins, color=color or 'steelblue', edgecolor='black', alpha=0.7)
            ax.set_xlabel(x_label or "数值")
            ax.set_ylabel(y_label or "频数")
            description = f"直方图展示了{len(values)}个数据点的分布情况"

        # 热力图
        elif chart_type == "heatmap":
            matrix = data.get("matrix", [])
            row_labels = data.get("row_labels", None)
            col_labels = data.get("col_labels", None)

            im = ax.imshow(matrix, cmap=opts.get("cmap", "RdYlBu_r"))
            fig.colorbar(im, ax=ax)

            if row_labels:
                ax.set_yticks(range(len(row_labels)))
                ax.set_yticklabels(row_labels)
            if col_labels:
                ax.set_xticks(range(len(col_labels)))
                ax.set_xticklabels(col_labels, rotation=45, ha='right')

            description = f"热力图展示了数据矩阵的相关性或强度分布"

        else:
            plt.close(fig)
            return json.dumps({
                "error": True,
                "message": f"不支持的图表类型: {chart_type}",
                "supported_types": ["bar", "line", "scatter", "pie", "boxplot", "histogram", "heatmap"]
            }, ensure_ascii=False)

        # 设置标题
        ax.set_title(title)

        # 调整布局
        plt.tight_layout()

        # 保存为字节流
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        image_bytes = buf.getvalue()
        plt.close(fig)

        # 编码为base64
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')

        result = {
            "success": True,
            "chart_type": chart_type,
            "title": title,
            "description": description,
            "image_base64": image_base64,
            "image_size_bytes": len(image_bytes)
        }

        # 尝试上传到Minio
        try:
            from infrastructure.storage.minio_client import get_minio_client
            minio_client = get_minio_client()
            if minio_client.is_available():
                url = minio_client.upload_bytes(
                    image_bytes,
                    content_type="image/png",
                    folder="research-visualizations"
                )
                if url:
                    result["image_url"] = url
                    logger.info(f"[ResearchToolsV2] 图表已上传到Minio")
        except Exception as e:
            logger.warning(f"[ResearchToolsV2] Minio上传失败: {e}")

        logger.info(f"[ResearchToolsV2] 可视化生成完成: {chart_type}")
        return json.dumps(result, ensure_ascii=False)

    except json.JSONDecodeError as e:
        return json.dumps({"error": True, "message": f"JSON解析失败: {str(e)}"}, ensure_ascii=False)
    except Exception as e:
        logger.error(f"[ResearchToolsV2] 可视化生成失败: {e}", exc_info=True)
        return json.dumps({"error": True, "message": f"可视化生成失败: {str(e)}"}, ensure_ascii=False)


# ========== 研究方案设计工具 ==========

@tool
def design_research_protocol(
    research_question: str,
    study_type: str = None,
    additional_info: str = None
) -> str:
    """
    辅助设计研究方案，提供结构化的研究设计建议。

    Args:
        research_question: 研究问题或假设
        study_type: 研究类型（可选，不提供则推荐），可选值：
            - "rct": 随机对照试验
            - "cohort": 队列研究
            - "case_control": 病例对照研究
            - "cross_sectional": 横断面研究
            - "case_series": 病例系列
            - "meta_analysis": 荟萃分析
        additional_info: 额外信息，如研究背景、可用资源等

    Returns:
        JSON格式的研究方案设计建议，包含：
        - 推荐研究类型及理由
        - 样本量估算建议
        - 入排标准建议
        - 变量定义
        - 统计分析计划
        - 伦理考虑

    使用场景：
        - 设计临床研究方案
        - 准备伦理审查材料
        - 科研项目申报

    注意：
        - 此工具提供结构化指导，具体方案需医生根据实际情况调整
        - 样本量估算仅为参考，建议使用专业软件精确计算
    """
    try:
        result = {
            "research_question": research_question,
            "requested_study_type": study_type
        }

        # 研究类型推荐
        study_types_info = {
            "rct": {
                "name": "随机对照试验 (RCT)",
                "description": "金标准研究设计，适用于评估干预效果",
                "适用场景": ["比较治疗方案效果", "评估新药疗效", "验证手术方式优劣"],
                "证据等级": "I级",
                "优点": ["偏倚控制好", "因果推断强"],
                "缺点": ["成本高", "实施难度大", "可能有伦理限制"]
            },
            "cohort": {
                "name": "队列研究",
                "description": "前瞻性或回顾性观察研究，跟踪暴露与结局关系",
                "适用场景": ["研究危险因素", "疾病预后研究", "长期随访研究"],
                "证据等级": "II级",
                "优点": ["可计算发病率", "时间顺序明确"],
                "缺点": ["耗时长", "失访问题"]
            },
            "case_control": {
                "name": "病例对照研究",
                "description": "比较病例和对照的既往暴露差异",
                "适用场景": ["罕见病病因研究", "疾病危险因素探索"],
                "证据等级": "III级",
                "优点": ["适合罕见病", "快速经济"],
                "缺点": ["回忆偏倚", "选择偏倚"]
            },
            "cross_sectional": {
                "name": "横断面研究",
                "description": "特定时点的人群调查",
                "适用场景": ["患病率调查", "现况描述", "相关性探索"],
                "证据等级": "IV级",
                "优点": ["快速实施", "成本低"],
                "缺点": ["无法判断因果", "时间局限"]
            },
            "case_series": {
                "name": "病例系列",
                "description": "对一组相似病例的描述性总结",
                "适用场景": ["新疾病描述", "罕见病报告", "临床经验总结"],
                "证据等级": "V级",
                "优点": ["容易实施", "发现新问题"],
                "缺点": ["无对照", "选择偏倚大"]
            },
            "meta_analysis": {
                "name": "荟萃分析",
                "description": "系统综合多个研究结果",
                "适用场景": ["整合现有证据", "提高统计效能", "探索异质性来源"],
                "证据等级": "I级（高质量时）",
                "优点": ["证据综合", "效能高"],
                "缺点": ["依赖原始研究质量", "异质性问题"]
            }
        }

        # 如果指定了研究类型
        if study_type and study_type in study_types_info:
            result["study_design"] = study_types_info[study_type]
        else:
            # 推荐研究类型（基于关键词简单判断）
            question_lower = research_question.lower()
            if any(kw in question_lower for kw in ["疗效", "效果", "治疗", "干预", "对比"]):
                recommended = "rct"
            elif any(kw in question_lower for kw in ["危险因素", "风险", "预后", "随访"]):
                recommended = "cohort"
            elif any(kw in question_lower for kw in ["罕见", "病因", "为什么"]):
                recommended = "case_control"
            elif any(kw in question_lower for kw in ["患病率", "调查", "分布", "现状"]):
                recommended = "cross_sectional"
            elif any(kw in question_lower for kw in ["综述", "荟萃", "系统评价"]):
                recommended = "meta_analysis"
            else:
                recommended = "cohort"  # 默认推荐队列研究

            result["recommended_study_type"] = recommended
            result["study_design"] = study_types_info[recommended]
            result["all_options"] = {k: v["name"] for k, v in study_types_info.items()}

        # 研究方案模板
        result["protocol_template"] = {
            "1_研究背景与目的": {
                "研究背景": "[需填写：当前研究领域现状、存在的问题]",
                "研究目的": "[基于您的问题：" + research_question + "]",
                "研究假设": "[明确的研究假设或拟回答的问题]"
            },
            "2_研究对象": {
                "入选标准": [
                    "年龄范围",
                    "诊断标准",
                    "知情同意"
                ],
                "排除标准": [
                    "合并症",
                    "既往治疗史",
                    "无法配合随访者"
                ],
                "样本量估算": {
                    "方法": "根据主要结局指标、预期效应量、α和β错误水平计算",
                    "建议": "使用G*Power或PASS软件进行精确计算",
                    "考虑因素": ["失访率", "亚组分析需求"]
                }
            },
            "3_研究方法": {
                "研究设计": result["study_design"]["name"],
                "分组方法": "[如适用：随机化方法、分配隐藏]",
                "干预措施": "[实验组和对照组的具体干预]",
                "随访计划": "[随访时间点、随访内容]"
            },
            "4_结局指标": {
                "主要结局": "[最重要的效果指标]",
                "次要结局": ["[其他重要指标1]", "[其他重要指标2]"],
                "安全性指标": ["不良事件", "严重不良事件"]
            },
            "5_统计分析计划": {
                "描述性分析": "连续变量用均数±标准差，分类变量用频数和百分比",
                "主要分析": "[根据结局指标类型选择：t检验/卡方检验/Cox回归等]",
                "敏感性分析": "[针对缺失数据、方案偏离等的分析]",
                "软件": "SPSS/SAS/R/Stata"
            },
            "6_伦理考虑": {
                "伦理审批": "提交机构伦理委员会审批",
                "知情同意": "所有受试者签署书面知情同意书",
                "数据安全": "数据脱敏、保密存储",
                "利益冲突": "声明研究资金来源和潜在利益冲突"
            },
            "7_质量控制": {
                "培训": "研究人员统一培训",
                "数据核查": "双人录入、逻辑校验",
                "监查": "[如适用：定期数据安全监查]"
            }
        }

        # 常用样本量参考
        result["sample_size_reference"] = {
            "连续变量两组比较": "n = 2 × [(Zα/2 + Zβ)² × σ²] / δ²",
            "率的两组比较": "n = [Zα/2√(2p̄q̄) + Zβ√(p1q1+p2q2)]² / (p1-p2)²",
            "经验法则": {
                "小效应量": "每组约400例",
                "中效应量": "每组约65例",
                "大效应量": "每组约26例"
            },
            "建议": "使用专业软件（G*Power、PASS）进行精确计算，考虑失访率增加10-20%"
        }

        if additional_info:
            result["additional_context"] = additional_info

        logger.info(f"[ResearchToolsV2] 研究方案设计完成")
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"[ResearchToolsV2] 研究方案设计失败: {e}", exc_info=True)
        return json.dumps({"error": True, "message": f"研究方案设计失败: {str(e)}"}, ensure_ascii=False)


# ========== 阶段二工具列表 ==========

PHASE2_TOOLS = [
    statistical_analysis,
    summarize_medical_literature,
    generate_research_visualization,
    design_research_protocol,
]


# ========== 模块信息 ==========
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("Research Tools V2 (阶段二) 模块信息")
    print("=" * 50)
    print(f"pandas/numpy 可用: {PANDAS_AVAILABLE}")
    print(f"scipy 可用: {SCIPY_AVAILABLE}")
    print(f"matplotlib 可用: {MATPLOTLIB_AVAILABLE}")
    print(f"\n阶段二工具数量: {len(PHASE2_TOOLS)}")

    for i, tool in enumerate(PHASE2_TOOLS, 1):
        print(f"  {i}. {tool.name}")
