# 药物表设计

## 概述
药物表用于管理医院中所有药品的信息，包含药品的基本信息、库存、价格、状态等。通过该表，医院能够有效地管理药品数据，进行库存控制、处方管理、药品追踪等。

## 字段设计

| 字段名称            | 数据类型         | 描述                                      | 示例                       |
|-------------------|----------------|-----------------------------------------|--------------------------|
| `drug_id`         | `VARCHAR(20)`   | 药物唯一标识符，通常为编号或编码。                 | `D1001`                   |
| `drug_name`       | `VARCHAR(255)`  | 药物名称，通常为通用名或商品名。                  | `阿莫西林`                 |
| `drug_category`   | `VARCHAR(100)`  | 药物类别，如抗生素、止痛药等。                   | `抗生素`                   |
| `drug_specification` | `VARCHAR(100)`  | 药物的规格，如剂量、包装规格等。                  | `500mg/片`                 |
| `drug_dosage_form` | `VARCHAR(50)`   | 药物的剂型，如片剂、注射剂等。                    | `片剂`                     |
| `manufacturer`    | `VARCHAR(255)`  | 药物的生产厂家或制药公司名称。                   | `华东制药厂`               |
| `batch_number`    | `VARCHAR(50)`   | 药物的生产批次编号，用于追溯药品来源。               | `20231122`                 |
| `expiry_date`     | `DATE`          | 药物的有效期。                                  | `2026-12-31`               |
| `price`           | `DECIMAL(10, 2)`| 药物的价格。                                    | `20.50`                    |
| `stock_quantity`  | `INT`           | 药物的库存量。                                  | `1000`                     |
| `is_prescription_drug` | `BOOLEAN`     | 标识该药物是否需要处方才能购买。                   | `TRUE` 或 `YES`            |
| `drug_status`     | `ENUM`          | 药物的状态，如在售、停用、下架等。                 | `在售`                     |
| `warning_info`    | `TEXT`          | 药物的警示信息，如过敏、禁忌症等。                  | `对青霉素过敏者禁用`         |
| `drug_description`| `TEXT`          | 药物的详细描述，包括药理作用、适应症等。             | `用于治疗细菌感染，适应症包括咽炎、肺炎等` |
| `created_at`      | `DATETIME`      | 记录创建的时间。                                 | `2025-11-17 10:30:00`       |
| `updated_at`      | `DATETIME`      | 记录最后一次更新时间。                            | `2025-11-17 10:45:00`       |
| `insurance_category` | `VARCHAR(100)` | 药品是否包含在医保目录中。                        | `医保目录`                 |

## 数据库表结构示例

```sql
CREATE TABLE drugs (
    drug_id VARCHAR(20) PRIMARY KEY,   -- 药物编号
    drug_name VARCHAR(255),            -- 药物名称
    drug_category VARCHAR(100),        -- 药物类别
    drug_specification VARCHAR(100),   -- 药物规格
    drug_dosage_form VARCHAR(50),      -- 剂型
    manufacturer VARCHAR(255),         -- 生产厂家
    batch_number VARCHAR(50),          -- 批号
    expiry_date DATE,                  -- 有效期
    price DECIMAL(10, 2),              -- 价格
    stock_quantity INT,                -- 库存量
    is_prescription_drug BOOLEAN,      -- 是否处方药
    drug_status ENUM('在售', '停用', '下架'),  -- 药物状态
    warning_info TEXT,                 -- 警示信息
    drug_description TEXT,             -- 药物描述
    created_at DATETIME,               -- 创建时间
    updated_at DATETIME,               -- 更新时间
    insurance_category VARCHAR(100)    -- 医保类别
);
