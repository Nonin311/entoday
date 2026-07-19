import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv
import json
import random
import math
# svgwrite 改为懒加载（仅 save_svg 需要），避免未安装时阻塞整个模块导入

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

class ScrollableFrame(tk.Frame):
    """
    可复用的滚动视图容器组件，用于节点/连线等动态行列表项。
    """
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )

        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width))

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")


class GridFlowchartApp:
    def __init__(self, root):
        self.root = root
        self.root.title("网格逻辑流程图设计器 v3.2")
        self.root.geometry("1280x820")
        self.root.minsize(1050, 700)
        
        # --- 核心数据结构 ---
        self.nodes = {}       # node_id -> {text, shape, row, col}
        self.connections = [] # list of {id, from_node_id, from_port, to_node_id, to_port, label, path_points}
        
        # 网格边界控制变量
        self.grid_bounds = {"min_col": 1, "max_col": 10, "min_row": 1, "max_row": 10}
        # 框图安全距离变量（两个节点的网格直线距离不能小于此值，防止节点过近穿透）
        self.MIN_GRID_DISTANCE = 1
        
        # 导入的几何体标准预设字典
        self.shape_templates = {}
        
        # 连线选择状态暂存
        self.active_port_selection = None
        
        # 网格像素常数
        self.GRID_X = 180
        self.GRID_Y = 100

        # 导出缩放系数
        self.export_scale = tk.StringVar(value="2.0")
        # 导出文字参数
        self.node_font_size = tk.StringVar(value="20")
        self.conn_font_size = tk.StringVar(value="16")
        self.label_offset = tk.StringVar(value="1.5")
        # 导出时是否显示网格线
        self.show_grid_lines = tk.BooleanVar(value=True)
        
        self.setup_ui()
        self.load_sample_data()
        self.trigger_redraw()

    def setup_ui(self):
        # 左右分栏
        main_pane = ttk.PanedWindow(self.root, orient="horizontal")
        main_pane.pack(fill="both", expand=True)
        
        # ==================== 左侧编辑控制区 ====================
        left_frame = ttk.Frame(main_pane)
        main_pane.add(left_frame, weight=4) # 占 40% 宽度
        
        left_pane = ttk.PanedWindow(left_frame, orient="vertical")
        left_pane.pack(fill="both", expand=True)
        
        # --- 1. 左侧上部总体控制面板 (30% 高度) ---
        top_ctrl = ttk.LabelFrame(left_pane, text="总体控制与配置面板 (v3.2)")
        left_pane.add(top_ctrl, weight=3)
        
        # 第一行：标题、版本、坐标界限
        row1 = ttk.Frame(top_ctrl)
        row1.pack(fill="x", padx=8, pady=4)
        ttk.Label(row1, text="控制台 v3.2 | ", font=("Microsoft YaHei", 9, "bold")).pack(side="left")
        
        ttk.Label(row1, text="列(Col):").pack(side="left", padx=2)
        self.min_col_var = tk.StringVar(value=str(self.grid_bounds["min_col"]))
        self.max_col_var = tk.StringVar(value=str(self.grid_bounds["max_col"]))
        ttk.Entry(row1, textvariable=self.min_col_var, width=3).pack(side="left")
        ttk.Label(row1, text="至").pack(side="left", padx=1)
        ttk.Entry(row1, textvariable=self.max_col_var, width=3).pack(side="left")
        
        ttk.Label(row1, text=" | 行(Row):").pack(side="left", padx=2)
        self.min_row_var = tk.StringVar(value=str(self.grid_bounds["min_row"]))
        self.max_row_var = tk.StringVar(value=str(self.grid_bounds["max_row"]))
        ttk.Entry(row1, textvariable=self.min_row_var, width=3).pack(side="left")
        ttk.Label(row1, text="至").pack(side="left", padx=1)
        ttk.Entry(row1, textvariable=self.max_row_var, width=3).pack(side="left")
        
        self.min_col_var.trace_add("write", self.on_bounds_change)
        self.max_col_var.trace_add("write", self.on_bounds_change)
        self.min_row_var.trace_add("write", self.on_bounds_change)
        self.max_row_var.trace_add("write", self.on_bounds_change)
        
        # 第二行：导入/导出及框图预设导入
        row2 = ttk.Frame(top_ctrl)
        row2.pack(fill="x", padx=8, pady=2)
        ttk.Button(row2, text="导入流程图 CSV", command=self.import_csv).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(row2, text="导出流程图 CSV", command=self.export_csv).pack(side="left", expand=True, fill="x", padx=2)
        
        # 载入标准框图的 JSON 配置文件
        ttk.Button(row2, text="导入框图定义JSON", command=self.import_shape_definitions).pack(side="left", expand=True, fill="x", padx=2)

        # 导出缩放比例
        ttk.Label(row2, text="缩放:").pack(side="left", padx=2)
        ttk.Entry(row2, textvariable=self.export_scale, width=4).pack(side="left", padx=2)
        ttk.Label(row2, text="框字号:").pack(side="left", padx=2)
        ttk.Entry(row2, textvariable=self.node_font_size, width=3).pack(side="left", padx=2)
        ttk.Label(row2, text="线字号:").pack(side="left", padx=2)
        ttk.Entry(row2, textvariable=self.conn_font_size, width=3).pack(side="left", padx=2)
        ttk.Label(row2, text="线标偏移:").pack(side="left", padx=2)
        ttk.Entry(row2, textvariable=self.label_offset, width=3).pack(side="left", padx=2)

        ttk.Checkbutton(row2, text="网格线", variable=self.show_grid_lines).pack(side="left", padx=4)

        # 高清导出选择（SVG / PNG / PDF）
        exp_btn = ttk.Button(row2, text="导出高画质图 (SVG/PNG/PDF)",
                             command=self._show_export_menu)
        exp_btn.pack(side="left", expand=True, fill="x", padx=2)
        
        # 第三行：双击添加节点
        row3 = ttk.LabelFrame(top_ctrl, text="双击卡片添加对应几何框图 (随机合法坐标)")
        row3.pack(fill="x", padx=8, pady=4)
        
        presets = [("Oval", "● 起止框", "#ECEFF1"), ("Rectangle", "■ 处理框", "#E8F5E9"), 
                   ("Hexagon", "⬡ 判断框", "#FFF3E0"), ("Octagon", "⯃ 输出框", "#E3F2FD")]
        for p_shape, p_title, p_color in presets:
            lbl = tk.Label(row3, text=p_title, bg=p_color, fg="#2c3e50", relief="groove", bd=1, padx=6, pady=4, cursor="hand2")
            lbl.pack(side="left", expand=True, fill="x", padx=2, pady=2)
            lbl.bind("<Double-Button-1>", lambda e, s=p_shape: self.add_random_node_with_check(s))

        # --- 2. 左侧下部框图连线编辑面板 (70% 高度) ---
        bottom_frame = ttk.Frame(left_pane)
        left_pane.add(bottom_frame, weight=7)
        
        v_split = ttk.PanedWindow(bottom_frame, orient="vertical")
        v_split.pack(fill="both", expand=True)
        
        # 节点编辑
        node_edit_f = ttk.LabelFrame(v_split, text="框图属性配置")
        v_split.add(node_edit_f, weight=1)
        self.nodes_scroll = ScrollableFrame(node_edit_f)
        self.nodes_scroll.pack(fill="both", expand=True)
        
        # 连线编辑
        conn_edit_f = ttk.LabelFrame(v_split, text="连线与自定义拐点路由")
        v_split.add(conn_edit_f, weight=1)
        self.conns_scroll = ScrollableFrame(conn_edit_f)
        self.conns_scroll.pack(fill="both", expand=True)

        # 拐点使用说明（连线面板右下角）
        hint_text = (
            "⚠ 强制拐点建议仅用于人工作图的美观化调整，\n"
            "不建议在自动化调用程序中使用。\n"
            "拐点格式：列,行; 列,行 …  (如: 6,1; 8,3)"
        )
        hint_lbl = tk.Label(conn_edit_f, text=hint_text, font=("Microsoft YaHei", 9),
                            fg="#1F2937", justify="left", anchor="se")
        hint_lbl.pack(side="bottom", anchor="se", padx=6, pady=4)
        
        # ==================== 右侧 Canvas 逻辑预览区 ====================
        right_frame = ttk.LabelFrame(main_pane, text="网格坐标逻辑预览图 (彩色点线模式)")
        main_pane.add(right_frame, weight=6) # 占 60% 宽度
        
        self.canvas = tk.Canvas(right_frame, bg="#FDFDFD", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=5, pady=5)
        self.canvas.bind("<Configure>", lambda e: self.trigger_redraw())

    # ==================== 核心逻辑：数据转换与路由算法 ====================
    
    def on_bounds_change(self, *args):
        try:
            min_c = int(self.min_col_var.get())
            max_c = int(self.max_col_var.get())
            min_r = int(self.min_row_var.get())
            max_r = int(self.max_row_var.get())
            if min_c > 0 and max_c >= min_c and min_r > 0 and max_r >= min_r:
                self.grid_bounds = {"min_col": min_c, "max_col": max_c, "min_row": min_r, "max_row": max_r}
                self.trigger_redraw()
        except ValueError:
            pass

    def add_random_node_with_check(self, shape_type):
        """
        根据安全距离变量检测，随机添加至合法的网格交叉点
        """
        min_c, max_c = self.grid_bounds["min_col"], self.grid_bounds["max_col"]
        min_r, max_r = self.grid_bounds["min_row"], self.grid_bounds["max_row"]
        
        valid_positions = []
        for c in range(min_c, max_c + 1):
            for r in range(min_r, max_r + 1):
                # 安全距离距离校验
                is_safe = True
                for other_node in self.nodes.values():
                    dist = abs(other_node["col"] - c) + abs(other_node["row"] - r)
                    if dist < self.MIN_GRID_DISTANCE:
                        is_safe = False
                        break
                if is_safe:
                    valid_positions.append((c, r))
                    
        if not valid_positions:
            messagebox.showwarning("添加失败", "网格内已无满足安全防碰撞距离的可用位置。")
            return
            
        col, row = random.choice(valid_positions)
        new_id = f"node_{int(random.random() * 1000000)}"
        
        default_names = {"Oval": "开始", "Rectangle": "步骤", "Hexagon": "决策", "Octagon": "输出"}
        self.nodes[new_id] = {
            "text": default_names.get(shape_type, "节点"),
            "shape": shape_type,
            "row": row,
            "col": col
        }
        self.rebuild_node_editor()
        self.trigger_redraw()

    def _port_direction(self, port_name):
        """
        从端口名推断方向字母：N/N1/N2→N, S→S, E→E, W→W。
        兼容 shape_designer 导出的自定义端口名。
        """
        if not port_name:
            return 'N'
        return port_name[0].upper()

    def get_port_step_offset(self, port_name):
        """
        根据端口名计算向外一步的网格位移向量。
        自动从端口名提取方向（如 N1→N 方向）。
        """
        direction = self._port_direction(port_name)
        offsets = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}
        return offsets.get(direction, (0, 0))

    # ==================== 形状元数据辅助方法 ====================

    # 形状在网格中的显示尺寸（网格单位），用于数学坐标 → 网格坐标转换
    SHAPE_GRID_W = 1.0
    SHAPE_GRID_H = 0.7

    def _get_shape_meta(self, shape_name):
        """获取形状的元数据（bounding_box + 端口列表），兼容旧格式"""
        if shape_name in self.shape_templates:
            data = self.shape_templates[shape_name]
            if isinstance(data, dict):
                # 向后兼容：自动补全 bounding_box
                if "bounding_box" not in data:
                    xs = [v[0] for v in data.get("vertices", [[-60, -30], [60, -30], [60, 30], [-60, 30]])]
                    ys = [v[1] for v in data.get("vertices", [[-60, -30], [60, -30], [60, 30], [-60, 30]])]
                    data["bounding_box"] = [min(xs) - 5, min(ys) - 5, max(xs) + 5, max(ys) + 5]
                # 向后兼容：自动补全端口 extension
                bbox = data["bounding_box"]
                for p in data.get("ports", []):
                    if "extension" not in p:
                        px, py = p.get("x", 0), p.get("y", 0)
                        d_top, d_bot = bbox[3] - py, py - bbox[1]
                        d_r, d_l = bbox[2] - px, px - bbox[0]
                        edges = [(d_top, px, bbox[3] + 5, 'N'), (d_bot, px, bbox[1] - 5, 'S'),
                                 (d_r, bbox[2] + 5, py, 'E'), (d_l, bbox[0] - 5, py, 'W')]
                        _, ex, ey, ed = min(edges, key=lambda e: e[0])
                        p["extension"] = {"x": ex, "y": ey, "direction": ed}
                return data
        # 默认元数据（内置四种形状，含顶点坐标）
        _default_ports = [
            {"name": "N", "x": 0, "y": 30, "extension": {"x": 0, "y": 40, "direction": "N"}},
            {"name": "S", "x": 0, "y": -30, "extension": {"x": 0, "y": -40, "direction": "S"}},
            {"name": "E", "x": 60, "y": 0, "extension": {"x": 70, "y": 0, "direction": "E"}},
            {"name": "W", "x": -60, "y": 0, "extension": {"x": -70, "y": 0, "direction": "W"}},
        ]
        _defaults = {
            "Oval":      {"v": [[round(60*math.cos(2*math.pi*i/32),2), round(30*math.sin(2*math.pi*i/32),2)] for i in range(32)], "bbox": [-65,-35,65,35]},
            "Rectangle": {"v": [[-60,-30],[60,-30],[60,30],[-60,30]], "bbox": [-65,-35,65,35]},
            "Hexagon":   {"v": [[-60,0],[-40,30],[40,30],[60,0],[40,-30],[-40,-30]], "bbox": [-65,-35,65,35]},
            "Octagon":   {"v": [[-45,30],[45,30],[60,15],[60,-15],[45,-30],[-45,-30],[-60,-15],[-60,15]], "bbox": [-65,-35,65,35]},
        }
        info = _defaults.get(shape_name, _defaults["Rectangle"])
        return {
            "bounding_box": info["bbox"],
            "vertices": [list(v) for v in info["v"]],
            "ports": [dict(p) for p in _default_ports],
        }

    def _port_extension_offset(self, shape_name, port_name):
        """将端口引出线终点从数学坐标转换为网格偏移量 (dx, dy)"""
        meta = self._get_shape_meta(shape_name)
        bbox = meta["bounding_box"]
        math_w = bbox[2] - bbox[0]
        math_h = bbox[3] - bbox[1]
        if math_w <= 0:
            math_w = 130
        if math_h <= 0:
            math_h = 70
        for p in meta.get("ports", []):
            if p["name"] == port_name and "extension" in p:
                ext = p["extension"]
                return (ext["x"] / math_w * self.SHAPE_GRID_W,
                        ext["y"] / math_h * self.SHAPE_GRID_H)
        # 兜底：使用旧逻辑
        dc, dr = self.get_port_step_offset(port_name)
        return (dc * 0.35, dr * 0.35)

    def calculate_discrete_route(self, conn, from_offset=0.0, to_offset=0.0):
        """
        核心路由机制：
        接入点可能不直接落在整步网格上（如物理边缘）。
        路由逻辑：从接入点出发沿自己的轴线行进一格宽度，到达标准的网格点后，再在网格拓扑上运行 BFS 最短路径计算。
        from_offset / to_offset: 多线共享端口时沿边缘的垂直偏移量（网格单位）。
        """
        fn = self.nodes.get(conn["from_node_id"])
        tn = self.nodes.get(conn["to_node_id"])
        if not fn or not tn:
            return []

        # 1. 获取网格出发点与归宿点
        # 接入点按照其方位向外行进 1 步整网格
        dc1, dr1 = self.get_port_step_offset(conn["from_port"])
        grid_start = (fn["col"] + dc1, fn["row"] + dr1)

        dc2, dr2 = self.get_port_step_offset(conn["to_port"])
        grid_end = (tn["col"] + dc2, tn["row"] + dr2)

        # 2. 路由计算：自连 vs 普通连接
        if conn["from_node_id"] == conn["to_node_id"]:
            # ---- 自连（不同方向端口）：两个端点各向外延 1 格，BFS 绕开节点本体 ----
            node_center = (fn["col"], fn["row"])
            # 排除节点中心 + 邻格，但放行 grid_start / grid_end 本身
            excluded = {node_center}
            for dc, dr in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                excluded.add((node_center[0] + dc, node_center[1] + dr))
            excluded.discard(grid_start)
            excluded.discard(grid_end)
            grid_routes = self._bfs_shortest(grid_start, grid_end, excluded)
            if not grid_routes or len(grid_routes) < 2:
                # 兜底：正交绕行路径
                if dc1 == 0:  # N/S 端口 → 先水平绕开
                    detour = (node_center[0] + 2, grid_start[1])
                else:         # E/W 端口 → 先垂直绕开
                    detour = (grid_start[0], node_center[1] + 2)
                grid_routes = [grid_start, detour, grid_end]
        else:
            # ---- 普通连接：含用户强制拐点 ----
            grid_routes = self.find_grid_path(grid_start, grid_end, conn.get("path_points", []))

        # 3. 使用端口引出线终点（来自 shape_designer 的延申区域数据）
        # 引出线终点已位于延申矩形边界外侧，是连线的精确起止点
        # 垂直偏移：N/S 端口沿水平方向错开，E/W 端口沿垂直方向错开
        perp = {"N": (1, 0), "S": (1, 0), "E": (0, 1), "W": (0, 1)}
        pdx1, pdy1 = perp.get(self._port_direction(conn["from_port"]), (0, 0))
        pdx2, pdy2 = perp.get(self._port_direction(conn["to_port"]), (0, 0))

        start_dx, start_dy = self._port_extension_offset(fn["shape"], conn["from_port"])
        end_dx, end_dy = self._port_extension_offset(tn["shape"], conn["to_port"])

        actual_start = (fn["col"] + start_dx + pdx1 * from_offset,
                        fn["row"] + start_dy + pdy1 * from_offset)
        actual_end = (tn["col"] + end_dx + pdx2 * to_offset,
                      tn["row"] + end_dy + pdy2 * to_offset)

        # 4. 正交化：在所有线段中插入中间点，确保每段只在一个方向上变化（横平竖直）
        # 起点侧：E/W 端口先水平后垂直，N/S 端口先垂直后水平
        if abs(dc1) > 0:  # E/W 端口
            start_int = (grid_start[0], actual_start[1])
        else:             # N/S 端口
            start_int = (actual_start[0], grid_start[1])

        # 拼合路径
        # 优化：跳过 BFS 终点 grid_end，从倒数第二个网格点直接向 actual_end 正交延伸，
        # 避免端口偏移量产生细碎短线段（如 E 3格→S 2格→E 0.15格 → 变为 E 3.15格→S 2格）
        raw_path = [actual_start, start_int, grid_start]
        if len(grid_routes) > 1:
            # 去掉首点(grid_start, 已加入)和末点(grid_end, 用 intermediate 代替)
            trimmed = grid_routes[1:-1]
            raw_path.extend(trimmed)
            # 以去掉 grid_end 后的最后一个网格点为基准
            if trimmed:
                base_grid = trimmed[-1]
            else:
                base_grid = grid_start
            # 按目标端口方向决定正交折点：
            #   E/W 端口：先折到 actual_end 的 y，再水平进入
            #   N/S 端口：先折到 actual_end 的 x，再垂直进入
            if abs(dc2) > 0:  # E/W
                intermediate = (base_grid[0], actual_end[1])
            else:             # N/S
                intermediate = (actual_end[0], base_grid[1])
            raw_path.append(intermediate)
        else:
            raw_path.extend(grid_routes[1:])
        raw_path.append(actual_end)

        # 去除连续重复点
        final_discrete_path = [raw_path[0]]
        for pt in raw_path[1:]:
            if pt != final_discrete_path[-1]:
                final_discrete_path.append(pt)

        # 回溯清理和路径简化（强制拐点作为锚点，不可被删除）
        forced_pts = conn.get("path_points", [])
        anchors = set(tuple(fp) for fp in forced_pts)
        final_discrete_path = self._cleanup_backtrack(final_discrete_path, anchors)
        final_discrete_path = self._simplify_path(final_discrete_path, anchors)

        return final_discrete_path

    def _cleanup_backtrack(self, path, anchors=None):
        """
        清理 A→B→A 回溯模式（跨段拼接或强制拐点可能导致）。
        锚点集合中的点不会被删除。
        """
        anchors = anchors or set()
        pts = list(path)
        i = 1
        while i < len(pts) - 1:
            if pts[i - 1] == pts[i + 1]:
                # A → B → A 模式：B 就是 pts[i]
                if pts[i] in anchors:
                    # B 是锚点（强制拐点），不删除，跳过
                    i += 1
                    continue
                # 去掉 B 和第二个 A，保留一个 A
                pts.pop(i)      # 去掉 B
                pts.pop(i)      # 去掉第二个 A（已移位到 i）
            else:
                i += 1
        # 去重
        result = [pts[0]]
        for pt in pts[1:]:
            if pt != result[-1]:
                result.append(pt)
        return result

    def _simplify_path(self, path, anchors=None):
        """
        迭代化简正交路径，消除 W 形多余拐弯，保留最简 L 形路径。

        分两步交替进行直至收敛：
          1. 合并连续同向线段（V→V 在同 x / H→H 在同 y）
          2. 合并 H→V→H（水平→垂直→水平）和 V→H→V 模式

        例如：E→S→E→S（3 次拐弯）化简为 E→S（1 次拐弯）。

        anchors: 不可删除的锚点集合（如用户强制拐点），这些点不会被合并。
        """
        anchors = anchors or set()
        if len(path) < 3:
            return path

        pts = list(path)
        changed = True
        while changed:
            changed = False

            # ---- 第 1 步：合并连续同向线段（V→V 或 H→H） ----
            i = 1
            while i < len(pts) - 1:
                A, B, C = pts[i - 1], pts[i], pts[i + 1]
                # 三点的 x 全相同 → 连续垂直段，去掉中间点 B（除非 B 是锚点）
                if A[0] == B[0] == C[0]:
                    if B not in anchors:
                        pts.pop(i)
                        changed = True
                        break
                # 三点的 y 全相同 → 连续水平段，去掉中间点 B（除非 B 是锚点）
                if A[1] == B[1] == C[1]:
                    if B not in anchors:
                        pts.pop(i)
                        changed = True
                        break
                i += 1
            if changed:
                continue

            # ---- 第 2 步：合并 H→V→H 和 V→H→V 交替模式 ----
            i = 1
            while i < len(pts) - 2:
                A, B, C, D = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]

                # 模式 1：H→V→H（两段水平在同一方向，中间夹一段垂直）
                if A[1] == B[1] and B[0] == C[0] and C[1] == D[1]:
                    h1_dir = B[0] - A[0]
                    h2_dir = D[0] - C[0]
                    if (h1_dir > 0 and h2_dir > 0) or (h1_dir < 0 and h2_dir < 0) or \
                       abs(h1_dir) < 1e-9 or abs(h2_dir) < 1e-9:
                        # B 被替换位置，C 被删除；任一为锚点则跳过
                        if B not in anchors and C not in anchors:
                            pts[i] = (D[0], A[1])  # B → (end_x, start_y)
                            pts.pop(i + 1)          # 移除 C
                            changed = True
                            break

                # 模式 2：V→H→V（两段垂直在同一方向，中间夹一段水平）
                elif A[0] == B[0] and B[1] == C[1] and C[0] == D[0]:
                    v1_dir = B[1] - A[1]
                    v2_dir = D[1] - C[1]
                    if (v1_dir > 0 and v2_dir > 0) or (v1_dir < 0 and v2_dir < 0) or \
                       abs(v1_dir) < 1e-9 or abs(v2_dir) < 1e-9:
                        # B 被替换位置，C 被删除；任一为锚点则跳过
                        if B not in anchors and C not in anchors:
                            pts[i] = (A[0], D[1])  # B → (start_x, end_y)
                            pts.pop(i + 1)          # 移除 C
                            changed = True
                            break

                i += 1

        # 最终去重
        result = [pts[0]]
        for pt in pts[1:]:
            if pt != result[-1]:
                result.append(pt)
        return result

    def find_grid_path(self, start, end, custom_intermediates=None):
        """
        多段合并的最短路由寻路。
        """
        seq = [start]
        if custom_intermediates:
            seq.extend(custom_intermediates)
        seq.append(end)

        full_path = []
        for i in range(len(seq) - 1):
            segment = self._bfs_shortest(seq[i], seq[i + 1])
            if i > 0 and full_path:
                full_path.extend(segment[1:])
            else:
                full_path.extend(segment)
        return full_path

    def _bfs_shortest(self, start, end, excluded=None):
        """
        Dijkstra 最短路径：直行 cost=1，拐弯 cost=2，180° 掉头 cost=100。
        探索时优先走目标主方向（|Δx|与|Δy|中较大者），确保路径简洁、减少W形拐弯。
        """
        if start == end:
            return [start]
        excluded = excluded or set()

        margin = 8
        min_c = min(start[0], end[0]) - margin
        max_c = max(start[0], end[0]) + margin
        min_r = min(start[1], end[1]) - margin
        max_r = max(start[1], end[1]) + margin

        import heapq
        # (cost, path, prev_direction)
        heap = [(0, [start], None)]
        best = {}

        # 按目标主方向确定探索顺序：|dx|>=|dy| 时优先水平，否则优先垂直
        tdx = end[0] - start[0]
        tdy = end[1] - start[1]
        if abs(tdx) >= abs(tdy):
            ordered_dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)] if tdx > 0 \
                      else [(-1, 0), (1, 0), (0, 1), (0, -1)]
        else:
            ordered_dirs = [(0, 1), (0, -1), (1, 0), (-1, 0)] if tdy > 0 \
                      else [(0, -1), (0, 1), (1, 0), (-1, 0)]

        while heap:
            cost, path, prev_dir = heapq.heappop(heap)
            curr = path[-1]

            if curr == end:
                return path

            state = (curr, prev_dir)
            if state in best and best[state] < cost:
                continue

            for dc, dr in ordered_dirs:
                nxt = (curr[0] + dc, curr[1] + dr)
                if nxt in excluded:
                    continue
                if not (min_c <= nxt[0] <= max_c and min_r <= nxt[1] <= max_r):
                    continue

                if prev_dir is None:
                    move_cost = 1
                elif prev_dir == (-dc, -dr):
                    move_cost = 100  # 180° 掉头
                elif prev_dir == (dc, dr):
                    move_cost = 1   # 直行
                else:
                    move_cost = 2   # 90° 拐弯

                new_cost = cost + move_cost
                new_state = (nxt, (dc, dr))

                if new_state not in best or new_cost < best[new_state]:
                    best[new_state] = new_cost
                    heapq.heappush(heap, (new_cost, path + [nxt], (dc, dr)))

        # 寻路无解时的 L 型兜底直线
        p = [start]
        c, r = start[0], start[1]
        while c != end[0]:
            c += 1 if end[0] > c else -1
            p.append((c, r))
        while r != end[1]:
            r += 1 if end[1] > r else -1
            p.append((c, r))
        return p

    # ==================== 事件交互响应与编辑器控制 ====================

    def on_port_select(self, node_id, port, combo):
        """
        两步选择端口构建连线：先从下拉框选起点，再从下拉框选终点。
        """
        if self.active_port_selection is None:
            self.active_port_selection = (node_id, port, combo)
            combo.configure(foreground="#D32F2F")
        else:
            from_nid, from_p, prev_combo = self.active_port_selection
            prev_combo.configure(foreground="")
            self.active_port_selection = None

            if from_nid == node_id:
                if self._port_direction(from_p) == self._port_direction(port):
                    messagebox.showwarning("逻辑无效",
                        f"不支持同方向自连（{from_p}→{port}）。\n请选择不同方向的端口，如 N→S、E→W 等。")
                    return

            new_id = f"conn_{int(random.random() * 1000000)}"
            self.connections.append({
                "id": new_id,
                "from_node_id": from_nid,
                "from_port": from_p,
                "to_node_id": node_id,
                "to_port": port,
                "label": "新连线",
                "path_points": []
            })
            self.rebuild_conn_editor()
            self.trigger_redraw()

    def delete_node(self, node_id):
        if node_id in self.nodes:
            del self.nodes[node_id]
        self.connections = [c for c in self.connections if c["from_node_id"] != node_id and c["to_node_id"] != node_id]
        self.rebuild_node_editor()
        self.rebuild_conn_editor()
        self.trigger_redraw()

    def delete_connection(self, conn_id):
        self.connections = [c for c in self.connections if c["id"] != conn_id]
        self.rebuild_conn_editor()
        self.trigger_redraw()

    # ==================== 界面列表重绘构造 ====================

    def rebuild_node_editor(self):
        for child in self.nodes_scroll.scrollable_frame.winfo_children():
            child.destroy()
            
        headers = ["文本内容", "形状选择", "行 (Y)", "列 (X)", "端口选择 (依次点两点连线)", "操作"]
        for idx, h in enumerate(headers):
            lbl = ttk.Label(self.nodes_scroll.scrollable_frame, text=h, font=("Microsoft YaHei", 9, "bold"))
            lbl.grid(row=0, column=idx, padx=4, pady=3, sticky="w")
            
        for r_idx, (node_id, node) in enumerate(self.nodes.items(), start=1):
            # 文本修改
            txt_var = tk.StringVar(value=node["text"])
            txt_ent = ttk.Entry(self.nodes_scroll.scrollable_frame, textvariable=txt_var, width=12)
            txt_ent.grid(row=r_idx, column=0, padx=2, pady=2, sticky="we")
            txt_var.trace_add("write", lambda *a, nid=node_id, v=txt_var: self._update_node_fields(nid, "text", v.get()))
            
            # 形状选择
            shapes = list(self.shape_templates.keys()) if self.shape_templates else ["Oval", "Rectangle", "Hexagon", "Octagon"]
            sh_var = tk.StringVar(value=node["shape"])
            sh_combo = ttk.Combobox(self.nodes_scroll.scrollable_frame, textvariable=sh_var, values=shapes, width=10, state="readonly")
            sh_combo.grid(row=r_idx, column=1, padx=2, pady=2)
            sh_var.trace_add("write", lambda *a, nid=node_id, v=sh_var: self._update_node_fields(nid, "shape", v.get()))
            
            # 行列设定
            r_var = tk.StringVar(value=str(node["row"]))
            c_var = tk.StringVar(value=str(node["col"]))
            
            r_spin = ttk.Spinbox(self.nodes_scroll.scrollable_frame, from_=1, to=100, textvariable=r_var, width=4)
            r_spin.grid(row=r_idx, column=2, padx=2, pady=2)
            r_var.trace_add("write", lambda *a, nid=node_id, rv=r_var, cv=c_var: self._update_node_pos(nid, rv, cv))
            
            c_spin = ttk.Spinbox(self.nodes_scroll.scrollable_frame, from_=1, to=100, textvariable=c_var, width=4)
            c_spin.grid(row=r_idx, column=3, padx=2, pady=2)
            c_var.trace_add("write", lambda *a, nid=node_id, rv=r_var, cv=c_var: self._update_node_pos(nid, rv, cv))
            
            # 端口选择（按方向分组下拉框）
            p_frame = tk.Frame(self.nodes_scroll.scrollable_frame)
            p_frame.grid(row=r_idx, column=4, padx=2, pady=2)
            shape_ports = self._get_ports_for_shape(node["shape"])
            arrow_map = {"N": "↑", "S": "↓", "E": "→", "W": "←"}
            # 按方向分组
            groups = {}
            for port_info in shape_ports:
                d = self._port_direction(port_info["name"])
                groups.setdefault(d, []).append(port_info["name"])
            for d, names in groups.items():
                # 排序：无数字的排最前（N），带数字的升序（N1<N2）
                names_sorted = sorted(names, key=lambda n: (len(n) > 1, n[1:] if len(n) > 1 else ""))
                g = tk.Frame(p_frame)
                g.pack(side="left", padx=2)
                tk.Label(g, text=arrow_map.get(d, d), font=("Arial", 8)).pack(side="left")
                combo = ttk.Combobox(g, values=names_sorted, state="readonly", width=4)
                combo.set(names_sorted[0])
                combo.pack(side="left")
                combo.bind("<<ComboboxSelected>>",
                           lambda e, nid=node_id, cb=combo: self.on_port_select(nid, cb.get(), cb))
                
            # 删除
            del_btn = tk.Button(self.nodes_scroll.scrollable_frame, text="✕", fg="red", relief="flat", font=("Arial", 10, "bold"))
            del_btn.grid(row=r_idx, column=5, padx=4, pady=2)
            del_btn.configure(command=lambda nid=node_id: self.delete_node(nid))

    def _update_node_fields(self, node_id, key, val):
        if node_id in self.nodes:
            self.nodes[node_id][key] = val
            self.trigger_redraw()

    def _update_node_pos(self, node_id, r_var, c_var):
        try:
            r = int(r_var.get())
            c = int(c_var.get())
            # 防碰撞约束
            for nid, other in self.nodes.items():
                if nid != node_id and abs(other["row"] - r) + abs(other["col"] - c) < self.MIN_GRID_DISTANCE:
                    return
            if node_id in self.nodes:
                self.nodes[node_id]["row"] = r
                self.nodes[node_id]["col"] = c
                self.trigger_redraw()
        except ValueError:
            pass

    def rebuild_conn_editor(self):
        for child in self.conns_scroll.scrollable_frame.winfo_children():
            child.destroy()
            
        headers = ["关联端口", "连线文字", "强制拐点", "操作"]
        for idx, h in enumerate(headers):
            lbl = ttk.Label(self.conns_scroll.scrollable_frame, text=h, font=("Microsoft YaHei", 9, "bold"))
            lbl.grid(row=0, column=idx, padx=4, pady=3, sticky="w")

        # 设置列宽权重：第0列（关联端口）权重最大，确保宽裕显示
        self.conns_scroll.scrollable_frame.grid_columnconfigure(0, weight=3)
        self.conns_scroll.scrollable_frame.grid_columnconfigure(1, weight=1)
        self.conns_scroll.scrollable_frame.grid_columnconfigure(2, weight=1)
        self.conns_scroll.scrollable_frame.grid_columnconfigure(3, weight=0)

        for r_idx, conn in enumerate(self.connections, start=1):
            fn = self.nodes.get(conn["from_node_id"])
            tn = self.nodes.get(conn["to_node_id"])
            if not fn or not tn:
                continue

            desc = f"{fn['text']}({conn['from_port']})→{tn['text']}({conn['to_port']})"
            desc_lbl = ttk.Label(self.conns_scroll.scrollable_frame, text=desc, width=28, anchor="w")
            desc_lbl.grid(row=r_idx, column=0, padx=2, pady=2, sticky="we")
            
            # 文字编辑
            lbl_var = tk.StringVar(value=conn["label"])
            lbl_ent = ttk.Entry(self.conns_scroll.scrollable_frame, textvariable=lbl_var, width=12)
            lbl_ent.grid(row=r_idx, column=1, padx=2, pady=2, sticky="we")
            lbl_var.trace_add("write", lambda *a, cid=conn["id"], v=lbl_var: self._update_conn_label(cid, v.get()))
            
            # 自定义拐点
            pts_str = "; ".join([f"{pt[0]},{pt[1]}" for pt in conn.get("path_points", [])])
            pts_var = tk.StringVar(value=pts_str)
            pts_ent = ttk.Entry(self.conns_scroll.scrollable_frame, textvariable=pts_var, width=15)
            pts_ent.grid(row=r_idx, column=2, padx=2, pady=2, sticky="we")
            pts_var.trace_add("write", lambda *a, cid=conn["id"], v=pts_var: self._update_conn_path(cid, v.get()))
            
            # 删除按钮
            del_btn = tk.Button(self.conns_scroll.scrollable_frame, text="✕", fg="red", relief="flat", font=("Arial", 10, "bold"))
            del_btn.grid(row=r_idx, column=3, padx=4, pady=2)
            del_btn.configure(command=lambda cid=conn["id"]: self.delete_connection(cid))

    def _update_conn_label(self, conn_id, val):
        for conn in self.connections:
            if conn["id"] == conn_id:
                conn["label"] = val
                self.trigger_redraw()
                break

    def _update_conn_path(self, conn_id, val):
        pts = []
        if val.strip():
            for item in val.split(";"):
                item = item.strip()
                if not item: continue
                try:
                    parts = item.split(",")
                    if len(parts) == 2:
                        pts.append((int(parts[0]), int(parts[1])))
                except ValueError:
                    pass
        for conn in self.connections:
            if conn["id"] == conn_id:
                conn["path_points"] = pts
                self.trigger_redraw()
                break

    # ==================== 右侧逻辑效果画布渲染引擎 ====================

    def trigger_redraw(self):
        """
        实时绘制逻辑预览图：仅展示点轴网格与彩色拓扑连线。
        """
        canvas = self.canvas
        canvas.delete("all")
        
        W = canvas.winfo_width()
        H = canvas.winfo_height()
        if W <= 1 or H <= 1:
            W, H = 600, 600
            
        min_c, max_c = self.grid_bounds["min_col"], self.grid_bounds["max_col"]
        min_r, max_r = self.grid_bounds["min_row"], self.grid_bounds["max_row"]

        # 自动缩放：确保整个网格区域适配当前画布大小
        pad = 50
        avail_w = W - 2 * pad
        avail_h = H - 2 * pad
        cols_span = max(1, max_c - min_c)
        rows_span = max(1, max_r - min_r)
        total_w = (cols_span + 1) * self.GRID_X
        total_h = (rows_span + 1) * self.GRID_Y
        scale = min(1.0, avail_w / total_w, avail_h / total_h)
        gx = self.GRID_X * scale
        gy = self.GRID_Y * scale

        mid_col = (min_c + max_c) / 2
        mid_row = (min_r + max_r) / 2

        # 坐标投影闭包
        def to_px(col, row):
            px = (W / 2) + (col - mid_col) * gx
            py = (H / 2) - (row - mid_row) * gy  # Y轴向上增加
            return px, py
            
        # 1. 绘制无限填充网格（充满整个可视预览区域）
        grid_start_col = int(mid_col - (W / 2) / gx) - 1
        grid_end_col = int(mid_col + (W / 2) / gx) + 2
        grid_start_row = int(mid_row - (H / 2) / gy) - 1
        grid_end_row = int(mid_row + (H / 2) / gy) + 2
        
        for c in range(grid_start_col, grid_end_col):
            px, _ = to_px(c, mid_row)
            # 合法设定边界内的网络线用深色，外部扩展填充区用浅色
            line_color = "#EBF0F2" if (c < min_c or c > max_c) else "#E2E8F0"
            line_width = 1 if (c < min_c or c > max_c) else 2
            canvas.create_line(px, 0, px, H, fill=line_color, width=line_width)
            # 画轴标
            canvas.create_text(px, H - 20, text=f"C{c}", fill="#90A4AE", font=("Arial", 8))
            
        for r in range(grid_start_row, grid_end_row):
            _, py = to_px(mid_col, r)
            line_color = "#EBF0F2" if (r < min_r or r > max_r) else "#E2E8F0"
            line_width = 1 if (r < min_r or r > max_r) else 2
            canvas.create_line(0, py, W, py, fill=line_color, width=line_width)
            canvas.create_text(20, py, text=f"R{r}", fill="#90A4AE", font=("Arial", 8))

        # 2. 绘制多路径彩色直角连线（含多线共享端口偏移）
        color_palette = ["#3B82F6", "#EC4899", "#10B981", "#F59E0B", "#8B5CF6", "#14B8A6"]

        # ---- 计算共享端口偏移量（同节点同方向多条连线时沿边缘错开） ----
        port_usage = {}
        for conn in self.connections:
            f_key = (conn["from_node_id"], conn["from_port"])
            t_key = (conn["to_node_id"], conn["to_port"])
            port_usage[f_key] = port_usage.get(f_key, 0) + 1
            port_usage[t_key] = port_usage.get(t_key, 0) + 1

        port_counters = {}
        conn_offsets = {}
        OFFSET_STEP = 0.12  # 网格单位
        for conn in self.connections:
            f_key = (conn["from_node_id"], conn["from_port"])
            t_key = (conn["to_node_id"], conn["to_port"])

            fc = port_usage.get(f_key, 1)
            from_idx = port_counters.get(f_key, 0)
            port_counters[f_key] = from_idx + 1
            from_offset = (from_idx - (fc - 1) / 2.0) * OFFSET_STEP if fc > 1 else 0.0

            tc = port_usage.get(t_key, 1)
            to_idx = port_counters.get(t_key, 0)
            port_counters[t_key] = to_idx + 1
            to_offset = (to_idx - (tc - 1) / 2.0) * OFFSET_STEP if tc > 1 else 0.0

            conn_offsets[conn["id"]] = (from_offset, to_offset)

        for idx, conn in enumerate(self.connections):
            from_off, to_off = conn_offsets.get(conn["id"], (0.0, 0.0))
            disc_pts = self.calculate_discrete_route(conn, from_off, to_off)
            if len(disc_pts) < 2:
                continue

            px_list = []
            for col_f, row_f in disc_pts:
                px_list.extend(to_px(col_f, row_f))

            line_color = color_palette[idx % len(color_palette)]

            # 画出带箭头的连续折线
            canvas.create_line(px_list, fill=line_color, width=3, arrow=tk.LAST, arrowshape=(8, 10, 3))

            # 绘制连线文字，带轻微垂直偏移量防止太贴近线条
            if conn["label"]:
                n_points = len(px_list) // 2  # 每点占 2 个元素 (x, y)
                if n_points >= 3:
                    mid = n_points // 2
                    mx = (px_list[mid * 2] + px_list[mid * 2 + 2]) / 2
                    my = (px_list[mid * 2 + 1] + px_list[mid * 2 + 3]) / 2
                    canvas.create_text(mx, my - 12, text=conn["label"], fill="#374151",
                                       font=("Microsoft YaHei", 8, "bold"))
                elif n_points == 2:
                    mx = (px_list[0] + px_list[2]) / 2
                    my = (px_list[1] + px_list[3]) / 2
                    canvas.create_text(mx, my - 12, text=conn["label"], fill="#374151",
                                       font=("Microsoft YaHei", 8, "bold"))
                
        # 3. 绘制节点逻辑圆点（不同颜色表示不同节点形状类型）
        shape_colors = {
            "Oval": "#EF4444",       # 起止框（红）
            "Rectangle": "#10B981",  # 处理框（绿）
            "Hexagon": "#F59E0B",    # 判断框（黄）
            "Octagon": "#3B82F6"     # 输出框（蓝）
        }
        for node in self.nodes.values():
            px, py = to_px(node["col"], node["row"])
            color = shape_colors.get(node["shape"], "#6B7280")
            
            # 逻辑圆点，直径16，比物理框图精致紧凑
            canvas.create_oval(px - 8, py - 8, px + 8, py + 8, fill=color, outline="#FFFFFF", width=2)
            canvas.create_text(px, py - 18, text=node["text"], fill="#1F2937", font=("Microsoft YaHei", 9, "bold"))

    # ==================== 外部框图标准 JSON 预设导入 ====================

    def _get_ports_for_shape(self, shape_name):
        """
        获取某形状的端口列表（含 extension 数据）。
        通过 _get_shape_meta 统一处理，自动兼容旧格式。
        """
        meta = self._get_shape_meta(shape_name)
        return meta.get("ports", [])

    def load_shape_definitions(self, filepath):
        """
        从指定文件路径加载框图定义JSON（纯逻辑，无GUI交互，可供外部代码调用）。

        参数:
            filepath: JSON 配置文件的绝对或相对路径
        返回:
            int: 成功加载的形状定义数量
        异常:
            FileNotFoundError: 文件不存在
            ValueError: JSON 格式不正确
        """
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("JSON 根元素必须是字典，当前类型: " + type(data).__name__)
        self.shape_templates = data
        return len(data)

    def import_shape_definitions(self):
        """
        GUI包装：通过文件对话框导入框图定义JSON。
        导入后自动刷新节点下拉框。
        """
        file_path = filedialog.askopenfilename(filetypes=[("框图配置文件", "*.json")])
        if not file_path:
            return
        try:
            count = self.load_shape_definitions(file_path)
            self.rebuild_node_editor()
            messagebox.showinfo("导入成功", f"成功导入 {count} 个标准几何体定义（含自定义端口），节点下拉框已就绪。")
        except Exception as e:
            messagebox.showerror("导入出错", f"无法解析该几何文件:\n{str(e)}")

    # ==================== 数据文件持久化与导入导出 ====================

    def save_csv(self, filepath):
        """
        保存流程图数据为CSV文件（纯逻辑，无GUI交互，可供外部代码调用）。

        参数:
            filepath: 目标 CSV 文件的绝对或相对路径
        """
        with open(filepath, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["BOUNDS", self.grid_bounds["min_col"], self.grid_bounds["max_col"],
                             self.grid_bounds["min_row"], self.grid_bounds["max_row"]])
            for nid, n in self.nodes.items():
                writer.writerow(["NODE", nid, n["text"], n["shape"], n["row"], n["col"]])
            for c in self.connections:
                pts_str = ";".join([f"{pt[0]},{pt[1]}" for pt in c.get("path_points", [])])
                writer.writerow(["CONN", c["id"], c["from_node_id"], c["from_port"],
                                 c["to_node_id"], c["to_port"], c["label"], pts_str])

    def export_csv(self):
        """GUI包装：通过文件对话框导出流程图CSV。"""
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV 文件", "*.csv")])
        if not file_path: return
        try:
            self.save_csv(file_path)
            messagebox.showinfo("成功", "流程图数据已顺利保存。")
        except Exception as e:
            messagebox.showerror("导出错误", f"失败: {str(e)}")

    def load_csv(self, filepath):
        """
        从指定文件路径加载流程图CSV数据（纯逻辑，无GUI交互，可供外部代码调用）。

        参数:
            filepath: CSV 文件的绝对或相对路径
        返回:
            tuple: (node_count, connection_count)
        """
        new_nodes = {}
        new_connections = []
        new_bounds = self.grid_bounds.copy()
        with open(filepath, mode='r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if not row or len(row) < 2: continue
                tag = row[0]
                if tag == "BOUNDS":
                    new_bounds = {"min_col": int(row[1]), "max_col": int(row[2]),
                                  "min_row": int(row[3]), "max_row": int(row[4])}
                elif tag == "NODE":
                    new_nodes[row[1]] = {"text": row[2], "shape": row[3],
                                         "row": int(row[4]), "col": int(row[5])}
                elif tag == "CONN":
                    pts = []
                    if len(row) > 7 and row[7].strip():
                        for item in row[7].split(";"):
                            parts = item.split(",")
                            if len(parts) == 2: pts.append((int(parts[0]), int(parts[1])))
                    new_connections.append({
                        "id": row[1], "from_node_id": row[2], "from_port": row[3],
                        "to_node_id": row[4], "to_port": row[5], "label": row[6], "path_points": pts
                    })
        self.grid_bounds = new_bounds
        self.nodes = new_nodes
        self.connections = new_connections

        # 同步UI绑定变量（GUI模式下保持控件同步；无头模式下无害）
        self.min_col_var.set(str(new_bounds["min_col"]))
        self.max_col_var.set(str(new_bounds["max_col"]))
        self.min_row_var.set(str(new_bounds["min_row"]))
        self.max_row_var.set(str(new_bounds["max_row"]))

        return len(new_nodes), len(new_connections)

    def import_csv(self):
        """GUI包装：通过文件对话框导入流程图CSV并刷新界面。"""
        file_path = filedialog.askopenfilename(filetypes=[("CSV 文件", "*.csv")])
        if not file_path: return
        try:
            node_count, conn_count = self.load_csv(file_path)
            self.rebuild_node_editor()
            self.rebuild_conn_editor()
            self.trigger_redraw()
            messagebox.showinfo("成功", f"数据加载完成：{node_count} 个节点，{conn_count} 条连线。")
        except Exception as e:
            messagebox.showerror("导入错误", f"失败: {str(e)}")

    # ==================== SVG / PNG / PDF 导出 ====================

    def _get_export_scale(self):
        """读取用户设置的导出缩放系数"""
        try:
            return float(self.export_scale.get())
        except ValueError:
            return 1.5

    def _get_cjk_font(self, size):
        """获取支持中文的 PIL 字体（跨平台字体路径）"""
        paths = [
            # Windows
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/simsun.ttc",
            # macOS
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
            # Linux
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
            "/usr/share/fonts/truetype/arphic/uming.ttc",
        ]
        for p in paths:
            try:
                return ImageFont.truetype(p, size=size)
            except Exception:
                continue
        return ImageFont.load_default()

    def _get_node_font_size(self):
        try:
            return int(self.node_font_size.get())
        except ValueError:
            return 11

    def _get_conn_font_size(self):
        try:
            return int(self.conn_font_size.get())
        except ValueError:
            return 9

    def _get_label_offset(self):
        try:
            return float(self.label_offset.get())
        except ValueError:
            return 1.2

    def _export_setup(self):
        """计算导出画布尺寸和坐标变换闭包（应用用户缩放系数）"""
        s = self._get_export_scale()
        min_c = self.grid_bounds["min_col"]
        max_c = self.grid_bounds["max_col"]
        min_r = self.grid_bounds["min_row"]
        max_r = self.grid_bounds["max_row"]
        pad = int(60 * s)
        w = int(((max_c - min_c + 2) * self.GRID_X + 2 * 60) * s)
        h = int(((max_r - min_r + 2) * self.GRID_Y + 2 * 60) * s)

        def to_px(col, row):
            x = pad + (col - min_c + 0.5) * self.GRID_X * s
            y = pad + (max_r - row + 0.5) * self.GRID_Y * s
            return x, y

        return w, h, to_px, min_c, max_r

    def _show_export_menu(self):
        """在按钮正下方弹出导出格式选择菜单（统一按钮风格）"""
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="导出 SVG 格式", command=self.export_svg)
        menu.add_command(label="导出 PNG 格式", command=self.export_png)
        menu.add_command(label="导出 PDF 格式 (A4)", command=self.export_pdf)
        # 获取当前鼠标位置弹出菜单
        menu.post(self.root.winfo_pointerx(), self.root.winfo_pointery())
        self._export_popup = menu  # 保持引用防止垃圾回收

    # ==================== 纯逻辑导出方法（可供外部代码调用） ====================

    def save_svg(self, filepath):
        """
        保存 SVG 矢量流程图到指定路径（纯逻辑，无GUI交互，可供外部代码调用）。

        参数:
            filepath: 目标 SVG 文件的绝对或相对路径
        异常:
            ValueError: 当前无有效节点
            ImportError: svgwrite 未安装
        """
        import svgwrite  # 懒加载，仅在调用 save_svg 时需要
        if not self.nodes:
            raise ValueError("当前无有效节点，无法导出SVG")

        svg_w, svg_h, to_px, min_c, max_r = self._export_setup()
        dwg = svgwrite.Drawing(filepath, size=(f"{svg_w}px", f"{svg_h}px"))
        dwg.add(dwg.rect(insert=(0, 0), size=(svg_w, svg_h), fill='white'))

        # 网格线（浅灰，可通过 self.show_grid_lines 关闭）
        if self.show_grid_lines.get():
            for c in range(self.grid_bounds["min_col"], self.grid_bounds["max_col"] + 1):
                x1, _ = to_px(c, self.grid_bounds["min_row"])
                x2, _ = to_px(c, self.grid_bounds["max_row"])
                dwg.add(dwg.line((x1, to_px(c, self.grid_bounds["min_row"])[1]),
                                 (x2, to_px(c, self.grid_bounds["max_row"])[1]),
                                 stroke='#E8ECF0', stroke_width=1))
            for r in range(self.grid_bounds["min_row"], self.grid_bounds["max_row"] + 1):
                y = to_px(self.grid_bounds["min_col"], r)[1]
                dwg.add(dwg.line((to_px(self.grid_bounds["min_col"], r)[0], y),
                                 (to_px(self.grid_bounds["max_col"], r)[0], y),
                                 stroke='#E8ECF0', stroke_width=1))

        # 形状
        for node_id, node in self.nodes.items():
            cx, cy = to_px(node["col"], node["row"])
            self._draw_shape_svg(dwg, node["shape"], node["text"], cx, cy)

        # 连线
        self._draw_connections_svg(dwg, to_px)

        dwg.save()

    def save_png(self, filepath):
        """
        保存 PNG 位图流程图到指定路径（纯逻辑，无GUI交互，可供外部代码调用）。

        参数:
            filepath: 目标 PNG 文件的绝对或相对路径
        异常:
            ValueError: 当前无有效节点
            ImportError: Pillow 未安装
        """
        if not self.nodes:
            raise ValueError("当前无有效节点，无法导出PNG")
        if not HAS_PIL:
            raise ImportError("Pillow 未安装，请运行: pip install Pillow")

        img = self._render_to_pil_image(scale=1.0)
        img.save(filepath, 'PNG')

    def save_pdf(self, filepath):
        """
        保存 A4 PDF 流程图到指定路径（300dpi位图嵌入，纯逻辑，无GUI交互，可供外部代码调用）。

        参数:
            filepath: 目标 PDF 文件的绝对或相对路径
        异常:
            ValueError: 当前无有效节点
            ImportError: Pillow 未安装
        """
        if not self.nodes:
            raise ValueError("当前无有效节点，无法导出PDF")
        if not HAS_PIL:
            raise ImportError("Pillow 未安装，请运行: pip install Pillow")

        dpi = 300
        a4_w, a4_h = 210, 297  # mm
        margin_mm = 12
        img_w = int(a4_w / 25.4 * dpi)
        img_h = int(a4_h / 25.4 * dpi)
        margin = int(margin_mm / 25.4 * dpi)

        # 计算流程图实际像素尺寸
        raw_w, raw_h, _, _, _ = self._export_setup()
        fit_scale = min((img_w - 2 * margin) / raw_w, (img_h - 2 * margin) / raw_h, 1.0)

        img = self._render_to_pil_image(scale=fit_scale, canvas_w=img_w, canvas_h=img_h,
                                        offset_x=(img_w - raw_w * fit_scale) / 2,
                                        offset_y=(img_h - raw_h * fit_scale) / 2)
        img.save(filepath, 'PDF', resolution=dpi)

    # ==================== GUI 导出包装方法（含文件对话框和消息提示） ====================

    def export_svg(self):
        """GUI包装：通过文件对话框导出 SVG 矢量流程图。"""
        if not self.nodes:
            messagebox.showwarning("导出提示", "当前无有效节点。")
            return
        filepath = filedialog.asksaveasfilename(
            defaultextension=".svg", filetypes=[("SVG 矢量图 (*.svg)", "*.svg")])
        if not filepath:
            return
        try:
            self.save_svg(filepath)
            messagebox.showinfo("导出成功", f"SVG 已保存至:\n{filepath}")
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            messagebox.showerror("导出失败", f"渲染出错:\n{str(e)}\n\n详细追踪:\n{tb}")

    def export_png(self):
        """GUI包装：通过文件对话框导出 PNG 位图流程图。"""
        if not self.nodes:
            messagebox.showwarning("导出提示", "当前无有效节点。")
            return
        if not HAS_PIL:
            messagebox.showerror("缺少依赖", "Pillow 未安装，请运行: pip install Pillow")
            return
        filepath = filedialog.asksaveasfilename(
            defaultextension=".png", filetypes=[("PNG 位图 (*.png)", "*.png")])
        if not filepath:
            return
        try:
            self.save_png(filepath)
            messagebox.showinfo("导出成功", f"PNG 已保存至:\n{filepath}")
        except Exception as e:
            messagebox.showerror("导出失败", f"渲染出错:\n{str(e)}")

    def export_pdf(self):
        """GUI包装：通过文件对话框导出 A4 PDF 流程图。"""
        if not self.nodes:
            messagebox.showwarning("导出提示", "当前无有效节点。")
            return
        if not HAS_PIL:
            messagebox.showerror("缺少依赖", "Pillow 未安装，请运行: pip install Pillow")
            return
        filepath = filedialog.asksaveasfilename(
            defaultextension=".pdf", filetypes=[("PDF 文档 (*.pdf)", "*.pdf")])
        if not filepath:
            return
        try:
            self.save_pdf(filepath)
            messagebox.showinfo("导出成功", f"PDF 已保存至:\n{filepath}")
        except Exception as e:
            messagebox.showerror("导出失败", f"渲染出错:\n{str(e)}")

    def _draw_shape_svg(self, dwg, shape_name, label, cx_px, cy_px):
        """在 SVG 中绘制一个形状（无端口/延申框，加粗线条）"""
        meta = self._get_shape_meta(shape_name)
        bbox = meta["bounding_box"]
        math_w = bbox[2] - bbox[0] if (bbox[2] - bbox[0]) > 0 else 130
        math_h = bbox[3] - bbox[1] if (bbox[3] - bbox[1]) > 0 else 70
        s = self._get_export_scale()
        sx = self.SHAPE_GRID_W / math_w * self.GRID_X * s
        sy = self.SHAPE_GRID_H / math_h * self.GRID_Y * s

        # 形状多边形（加粗）
        if "vertices" in meta and meta["vertices"]:
            pts = [(cx_px + v[0] * sx, cy_px - v[1] * sy) for v in meta["vertices"]]
            dwg.add(dwg.polygon(pts, fill='#F8FAFC', stroke='#475569', stroke_width=3,
                                stroke_linejoin='miter'))

        # 节点文字（svgwrite 要求 x/y 为可迭代对象，传单值需包装为列表）
        font_sz = max(8, int(self._get_node_font_size() * s))
        dwg.add(dwg.text(label, x=[cx_px], y=[cy_px], fill='#1F2937',
                        font_size=font_sz, font_family='Microsoft YaHei, SimHei, sans-serif',
                        text_anchor='middle', font_weight='bold'))

    def _draw_connections_svg(self, dwg, to_px):
        """在 SVG 中绘制所有连线（加粗）"""
        colors = ["#3B82F6", "#EC4899", "#10B981", "#F59E0B", "#8B5CF6", "#14B8A6"]
        port_usage = {}
        for conn in self.connections:
            f_key = (conn["from_node_id"], conn["from_port"])
            t_key = (conn["to_node_id"], conn["to_port"])
            port_usage[f_key] = port_usage.get(f_key, 0) + 1
            port_usage[t_key] = port_usage.get(t_key, 0) + 1
        port_counters = {}
        OFFSET_STEP = 0.12
        s = self._get_export_scale()

        for idx, conn in enumerate(self.connections):
            f_key = (conn["from_node_id"], conn["from_port"])
            t_key = (conn["to_node_id"], conn["to_port"])
            fc = port_usage.get(f_key, 1)
            fi = port_counters.get(f_key, 0)
            port_counters[f_key] = fi + 1
            from_off = (fi - (fc - 1) / 2.0) * OFFSET_STEP if fc > 1 else 0.0
            tc = port_usage.get(t_key, 1)
            ti = port_counters.get(t_key, 0)
            port_counters[t_key] = ti + 1
            to_off = (ti - (tc - 1) / 2.0) * OFFSET_STEP if tc > 1 else 0.0

            disc_pts = self.calculate_discrete_route(conn, from_off, to_off)
            if len(disc_pts) < 2:
                continue

            pts = [(to_px(c, r)[0], to_px(c, r)[1]) for c, r in disc_pts]
            color = colors[idx % len(colors)]
            dwg.add(dwg.polyline(pts, fill='none', stroke=color, stroke_width=2.5,
                                 stroke_linejoin='round'))

            # 箭头（最后一段）
            if len(pts) >= 2:
                ax, ay = pts[-2]
                bx, by = pts[-1]
                angle = math.atan2(by - ay, bx - ax)
                al = max(6, int(8 * s))
                x1 = bx - al * math.cos(angle - 0.5)
                y1 = by - al * math.sin(angle - 0.5)
                x2 = bx - al * math.cos(angle + 0.5)
                y2 = by - al * math.sin(angle + 0.5)
                dwg.add(dwg.polygon([(bx, by), (x1, y1), (x2, y2)],
                                    fill=color, stroke=color, stroke_width=1))

            # 标签（水平段放上方，垂直段放右侧，偏移量按字号比例）
            if conn["label"] and len(pts) >= 2:
                mid = len(pts) // 2
                if mid < 1:
                    mid = 1
                fs = max(6, int(self._get_conn_font_size() * s))
                off = max(2, int(fs * self._get_label_offset()))
                p1, p2 = pts[mid - 1], pts[mid]
                mx = (p1[0] + p2[0]) / 2
                my = (p1[1] + p2[1]) / 2
                if abs(p2[0] - p1[0]) > abs(p2[1] - p1[1]):
                    # 水平段 → 文字在上方
                    my -= off
                else:
                    # 垂直段 → 文字在右侧
                    mx += off
                dwg.add(dwg.text(conn["label"], x=[mx], y=[my], fill=color,
                                font_size=fs, font_family='Microsoft YaHei, SimHei, sans-serif',
                                text_anchor='middle', font_weight='bold'))

    def _render_to_pil_image(self, scale=1.0, canvas_w=None, canvas_h=None,
                             offset_x=0, offset_y=0):
        """生成 PIL Image 流程图（共用核心，供 PNG/PDF 调用）"""
        raw_w, raw_h, to_px, min_c, max_r = self._export_setup()

        if canvas_w is None:
            canvas_w = int(raw_w * scale)
        if canvas_h is None:
            canvas_h = int(raw_h * scale)

        img = Image.new('RGB', (canvas_w, canvas_h), 'white')
        draw = ImageDraw.Draw(img)

        def img_px(col, row):
            x, y = to_px(col, row)
            return int(x * scale + offset_x), int(y * scale + offset_y)

        # 中文字体
        font_size = max(6, int(self._get_conn_font_size() * scale))
        font = self._get_cjk_font(font_size)
        label_font = self._get_cjk_font(max(8, int(self._get_node_font_size() * scale)))

        # 网格线（可通过 self.show_grid_lines 关闭）
        if self.show_grid_lines.get():
            for c in range(self.grid_bounds["min_col"], self.grid_bounds["max_col"] + 1):
                x1, y1 = img_px(c, self.grid_bounds["min_row"])
                x2, y2 = img_px(c, self.grid_bounds["max_row"])
                draw.line([(x1, y1), (x2, y2)], fill='#E8ECF0', width=max(1, int(1 * scale)))

            for r in range(self.grid_bounds["min_row"], self.grid_bounds["max_row"] + 1):
                x1, y1 = img_px(self.grid_bounds["min_col"], r)
                x2, y2 = img_px(self.grid_bounds["max_col"], r)
                draw.line([(x1, y1), (x2, y2)], fill='#E8ECF0', width=max(1, int(1 * scale)))

        # 形状
        exp_s = self._get_export_scale()
        for node_id, node in self.nodes.items():
            cx, cy = img_px(node["col"], node["row"])
            self._draw_shape_pil(draw, node["shape"], node["text"], cx, cy, scale, exp_s, label_font)

        # 连线（加粗）
        colors = ["#3B82F6", "#EC4899", "#10B981", "#F59E0B", "#8B5CF6", "#14B8A6"]
        port_usage = {}
        for conn in self.connections:
            f_key = (conn["from_node_id"], conn["from_port"])
            t_key = (conn["to_node_id"], conn["to_port"])
            port_usage[f_key] = port_usage.get(f_key, 0) + 1
            port_usage[t_key] = port_usage.get(t_key, 0) + 1
        port_counters = {}
        OFFSET_STEP = 0.12

        for idx, conn in enumerate(self.connections):
            f_key = (conn["from_node_id"], conn["from_port"])
            t_key = (conn["to_node_id"], conn["to_port"])
            fc = port_usage.get(f_key, 1)
            fi = port_counters.get(f_key, 0)
            port_counters[f_key] = fi + 1
            from_off = (fi - (fc - 1) / 2.0) * OFFSET_STEP if fc > 1 else 0.0
            tc = port_usage.get(t_key, 1)
            ti = port_counters.get(t_key, 0)
            port_counters[t_key] = ti + 1
            to_off = (ti - (tc - 1) / 2.0) * OFFSET_STEP if tc > 1 else 0.0

            disc_pts = self.calculate_discrete_route(conn, from_off, to_off)
            if len(disc_pts) < 2:
                continue

            pts = [img_px(c, r) for c, r in disc_pts]
            color = colors[idx % len(colors)]
            lw = max(1, int(2.5 * scale))
            draw.line(pts, fill=color, width=lw)

            # 箭头
            if len(pts) >= 2:
                ax, ay = pts[-2]
                bx, by = pts[-1]
                angle = math.atan2(by - ay, bx - ax)
                al = max(4, int(8 * scale))
                x1 = bx - al * math.cos(angle - 0.5)
                y1 = by - al * math.sin(angle - 0.5)
                x2 = bx - al * math.cos(angle + 0.5)
                y2 = by - al * math.sin(angle + 0.5)
                draw.polygon([(bx, by), (x1, y1), (x2, y2)], fill=color)

            # 标签（水平段放上方，垂直段放右侧，偏移量按字号比例）
            if conn["label"] and len(pts) >= 2:
                mid = len(pts) // 2
                if mid < 1:
                    mid = 1
                off = max(2, int(font_size * self._get_label_offset()))
                p1, p2 = pts[mid - 1], pts[mid]
                mx = (p1[0] + p2[0]) / 2
                my = (p1[1] + p2[1]) / 2
                if abs(p2[0] - p1[0]) > abs(p2[1] - p1[1]):
                    my -= off  # 水平段 → 上方
                else:
                    mx += off  # 垂直段 → 右侧
                try:
                    tbbox = draw.textbbox((0, 0), conn["label"], font=font)
                    tw = tbbox[2] - tbbox[0]
                except AttributeError:
                    tw = len(conn["label"]) * font_size * 0.6
                draw.text((mx - tw / 2, my), conn["label"], fill=color, font=font)

        return img

    def _draw_shape_pil(self, draw, shape_name, label, cx_px, cy_px, scale, exp_s, font):
        """在 PIL Image 上绘制一个形状（无端口/延申框，加粗）"""
        meta = self._get_shape_meta(shape_name)
        bbox = meta["bounding_box"]
        math_w = bbox[2] - bbox[0] if (bbox[2] - bbox[0]) > 0 else 130
        math_h = bbox[3] - bbox[1] if (bbox[3] - bbox[1]) > 0 else 70
        sx = self.SHAPE_GRID_W / math_w * self.GRID_X * scale * exp_s
        sy = self.SHAPE_GRID_H / math_h * self.GRID_Y * scale * exp_s

        # 形状多边形（加粗）
        if "vertices" in meta and meta["vertices"]:
            pts = [(int(cx_px + v[0] * sx), int(cy_px - v[1] * sy)) for v in meta["vertices"]]
            lw = max(1, int(3 * scale))
            draw.polygon(pts, fill='#F8FAFC', outline='#475569', width=lw)

        # 节点文字
        try:
            tbbox = draw.textbbox((0, 0), label, font=font)
            tw = tbbox[2] - tbbox[0]
        except AttributeError:
            tw = len(label) * font.size * 0.6
        draw.text((cx_px - tw / 2, cy_px - font.size / 2), label, fill='#1F2937', font=font)

    def load_sample_data(self):
        """
        基础初始演示数据
        """
        self.nodes = {
            "n1": {"text": "开始", "shape": "Oval", "row": 7, "col": 2},
            "n2": {"text": "加载配置", "shape": "Rectangle", "row": 5, "col": 2},
            "n3": {"text": "检验通过?", "shape": "Hexagon", "row": 3, "col": 2},
            "n4": {"text": "退出", "shape": "Oval", "row": 1, "col": 2},
            "n5": {"text": "写入数据库", "shape": "Octagon", "row": 3, "col": 6}
        }
        self.connections = [
            {"id": "c1", "from_node_id": "n1", "from_port": "S", "to_node_id": "n2", "to_port": "N", "label": "启动", "path_points": []},
            {"id": "c2", "from_node_id": "n2", "from_port": "S", "to_node_id": "n3", "to_port": "N", "label": "验证", "path_points": []},
            {"id": "c3", "from_node_id": "n3", "from_port": "S", "to_node_id": "n4", "to_port": "N", "label": "失败", "path_points": []},
            {"id": "c4", "from_node_id": "n3", "from_port": "E", "to_node_id": "n5", "to_port": "W", "label": "成功", "path_points": []},
            {"id": "c5", "from_node_id": "n5", "from_port": "S", "to_node_id": "n4", "to_port": "E", "label": "回调", "path_points": [(6, 1)]}
        ]
        self.rebuild_node_editor()
        self.rebuild_conn_editor()


if __name__ == "__main__":
    root = tk.Tk()
    app = GridFlowchartApp(root)
    root.update()
    app.trigger_redraw()
    root.mainloop()