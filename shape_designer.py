import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import math
import svgwrite

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

class ShapeDesignerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("标准框图几何元设计器 v1.0 (Mind 3.0)")
        self.root.geometry("1100x700")
        self.root.minsize(950, 600)
        
        # --- 核心设计数据模型 ---
        # 顶点坐标列表: [[x1, y1], [x2, y2], ...] 范围限制在 [-100, 100]
        self.vertices = []
        # 手动指定的质心坐标: [x, y]
        self.centroid = [0, 0]
        # 接入端口列表: [{"name": "N", "x": 0, "y": 30}, ...]
        self.ports = []
        
        # 内存中的标准库，默认预装4种高精度框图
        self.shapes_library = self.get_default_library()
        self.current_shape_name = "CustomShape"
        
        # 初始化 UI 与事件绑定
        self.setup_ui()
        self.load_shape_to_editor("Rectangle") # 默认载入处理框

    def get_default_library(self):
        """
        预装已有内置框图的数据结构（标准规格）。
        数学坐标系中：X 向右增加，Y 向上增加，中心为 (0,0)。
        """
        # 1. 椭圆起止框（由参数方程 60*cos(t), 30*sin(t) 离散出32个点）
        oval_vertices = []
        for i in range(32):
            t = (2 * math.pi * i) / 32
            oval_vertices.append([round(60 * math.cos(t), 2), round(30 * math.sin(t), 2)])
            
        return {
            "Rectangle": {
                "vertices": [[-60, -30], [60, -30], [60, 30], [-60, 30]],
                "centroid": [0, 0],
                "ports": [
                    {"name": "N", "x": 0, "y": 30},
                    {"name": "S", "x": 0, "y": -30},
                    {"name": "E", "x": 60, "y": 0},
                    {"name": "W", "x": -60, "y": 0}
                ]
            },
            "Oval": {
                "vertices": oval_vertices,
                "centroid": [0, 0],
                "ports": [
                    {"name": "N", "x": 0, "y": 30},
                    {"name": "S", "x": 0, "y": -30},
                    {"name": "E", "x": 60, "y": 0},
                    {"name": "W", "x": -60, "y": 0}
                ]
            },
            "Hexagon": {
                "vertices": [[-60, 0], [-40, 30], [40, 30], [60, 0], [40, -30], [-40, -30]],
                "centroid": [0, 0],
                "ports": [
                    {"name": "N", "x": 0, "y": 30},
                    {"name": "S", "x": 0, "y": -30},
                    {"name": "E", "x": 60, "y": 0},
                    {"name": "W", "x": -60, "y": 0}
                ]
            },
            "Octagon": {
                "vertices": [[-45, 30], [45, 30], [60, 15], [60, -15], [45, -30], [-45, -30], [-60, -15], [-60, 15]],
                "centroid": [0, 0],
                "ports": [
                    {"name": "N", "x": 0, "y": 30},
                    {"name": "S", "x": 0, "y": -30},
                    {"name": "E", "x": 60, "y": 0},
                    {"name": "W", "x": -60, "y": 0}
                ]
            }
        }

    def setup_ui(self):
        # 左右分栏
        main_pane = ttk.PanedWindow(self.root, orient="horizontal")
        main_pane.pack(fill="both", expand=True)
        
        # ================= 左侧编辑面板 =================
        left_frame = ttk.Frame(main_pane)
        main_pane.add(left_frame, weight=4)
        
        # 标签页组织不同配置功能
        notebook = ttk.Notebook(left_frame)
        notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        # --- TAB 1: 预设管理与标准文件 I/O ---
        tab_io = ttk.Frame(notebook)
        notebook.add(tab_io, text=" 模板与文件 ")
        self.setup_io_tab(tab_io)
        
        # --- TAB 2: 函数生成线段 (核心功能) ---
        tab_func = ttk.Frame(notebook)
        notebook.add(tab_func, text=" 函数线段生成器 ")
        self.setup_function_tab(tab_func)
        
        # --- TAB 3: 质心与端口交互设置 ---
        tab_anchor = ttk.Frame(notebook)
        notebook.add(tab_anchor, text=" 质心与接入点 ")
        self.setup_anchor_tab(tab_anchor)

        # --- TAB 4: 导出与渲染 ---
        tab_export = ttk.Frame(notebook)
        notebook.add(tab_export, text=" 导出与渲染 ")
        self.setup_export_tab(tab_export)

        # ================= 右侧预览面板 =================
        right_frame = ttk.LabelFrame(main_pane, text="几何元归一化预览区 (数学坐标系限制: -100 到 100)")
        main_pane.add(right_frame, weight=6)
        
        # 预览 Canvas (固定比例尺)
        self.canvas = tk.Canvas(right_frame, bg="#FFFFFF", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=10, pady=10)
        self.canvas.bind("<Configure>", lambda e: self.draw_preview())

    # ================= 属性标签页 UI 构建及事件 =================

    def setup_io_tab(self, parent):
        # 1. 预设库载入
        g1 = ttk.LabelFrame(parent, text="从内置标准库载入几何体")
        g1.pack(fill="x", padx=10, pady=10)
        
        self.preset_combo = ttk.Combobox(g1, values=list(self.shapes_library.keys()), state="readonly")
        self.preset_combo.set("Rectangle")
        self.preset_combo.pack(side="left", fill="x", expand=True, padx=10, pady=10)
        
        btn_load = ttk.Button(g1, text="载入到编辑器", command=self.on_load_preset_clicked)
        btn_load.pack(side="left", padx=10, pady=10)
        
        # 2. 保存到库
        g2 = ttk.LabelFrame(parent, text="保存当前几何体至本地内存库")
        g2.pack(fill="x", padx=10, pady=10)
        
        ttk.Label(g2, text="几何元名称:").pack(side="left", padx=10, pady=10)
        self.shape_name_var = tk.StringVar(value="CustomShape")
        ent_name = ttk.Entry(g2, textvariable=self.shape_name_var, width=15)
        ent_name.pack(side="left", fill="x", expand=True, padx=5, pady=10)
        
        btn_save_mem = ttk.Button(g2, text="保存/覆盖", command=self.save_current_to_library)
        btn_save_mem.pack(side="left", padx=10, pady=10)
        
        # 3. 标准配置文件导出导入
        g3 = ttk.LabelFrame(parent, text="标准库文件 I/O (JSON格式)")
        g3.pack(fill="both", expand=True, padx=10, pady=10)
        
        info_lbl = ttk.Label(g3, text="此标准文件将作为配置文件，\n直接供后续的流程图布局渲染器读取。", justify="left", foreground="#555555")
        info_lbl.pack(pady=15, padx=10)
        
        btn_import = ttk.Button(g3, text="导入外部标准配置文件 (.json)", command=self.import_standard_file)
        btn_import.pack(fill="x", padx=20, pady=10)
        
        btn_export = ttk.Button(g3, text="导出当前标准配置文件 (.json)", command=self.export_standard_file)
        btn_export.pack(fill="x", padx=20, pady=10)

    def setup_function_tab(self, parent):
        info_lbl = ttk.Label(parent, text="输入含有参数 't' 的数学方程，生成连续闭合线段点：", foreground="#555555")
        info_lbl.pack(anchor="w", padx=15, pady=8)
        
        # 公式输入区域
        f_frame = ttk.Frame(parent)
        f_frame.pack(fill="x", padx=15, pady=5)
        f_frame.columnconfigure(1, weight=1)

        ttk.Label(f_frame, text="X(t) = ").grid(row=0, column=0, sticky="w", pady=5)
        self.func_x_var = tk.StringVar(value="60 * cos(t)")
        ttk.Entry(f_frame, textvariable=self.func_x_var, width=30).grid(row=0, column=1, sticky="ew", pady=5)
        
        ttk.Label(f_frame, text="Y(t) = ").grid(row=1, column=0, sticky="w", pady=5)
        self.func_y_var = tk.StringVar(value="30 * sin(t)")
        ttk.Entry(f_frame, textvariable=self.func_y_var, width=30).grid(row=1, column=1, sticky="ew", pady=5)
        
        # 参数范围
        r_frame = ttk.Frame(parent)
        r_frame.pack(fill="x", padx=15, pady=5)
        
        ttk.Label(r_frame, text="t 最小值:").grid(row=0, column=0, sticky="w", pady=3)
        self.t_min_var = tk.StringVar(value="0")
        ttk.Entry(r_frame, textvariable=self.t_min_var, width=10).grid(row=0, column=1, sticky="w", pady=3, padx=5)
        
        ttk.Label(r_frame, text="t 最大值:").grid(row=0, column=2, sticky="w", pady=3, padx=10)
        self.t_max_var = tk.StringVar(value="2 * pi")
        ttk.Entry(r_frame, textvariable=self.t_max_var, width=10).grid(row=0, column=3, sticky="w", pady=3)
        
        ttk.Label(r_frame, text="采样段数:").grid(row=1, column=0, sticky="w", pady=5)
        self.t_steps_var = tk.StringVar(value="32")
        ttk.Entry(r_frame, textvariable=self.t_steps_var, width=10).grid(row=1, column=1, sticky="w", pady=5, padx=5)
        
        # 快捷公式
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill="x", padx=15, pady=10)
        
        ttk.Button(btn_frame, text="重设公式为椭圆", command=lambda: self.set_preset_formula("60*cos(t)", "30*sin(t)", "0", "2*pi")).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(btn_frame, text="重设公式为玫瑰线", command=lambda: self.set_preset_formula("70*cos(3*t)*cos(t)", "70*cos(3*t)*sin(t)", "0", "pi")).pack(side="left", expand=True, fill="x", padx=2)
        
        # 触发生成按钮
        btn_gen = ttk.Button(parent, text="▶ 计算方程并生成外廓线段", command=self.generate_vertices_from_function)
        btn_gen.pack(fill="x", padx=15, pady=15)

    def setup_anchor_tab(self, parent):
        # 1. 质心手动设置
        g1 = ttk.LabelFrame(parent, text="手动指定物理质点 (Centroid)")
        g1.pack(fill="x", padx=10, pady=10)
        
        self.cen_x_var = tk.StringVar(value="0")
        self.cen_y_var = tk.StringVar(value="0")
        
        ttk.Label(g1, text="X坐标:").pack(side="left", padx=5, pady=10)
        ttk.Entry(g1, textvariable=self.cen_x_var, width=6).pack(side="left", padx=5, pady=10)
        ttk.Label(g1, text="Y坐标:").pack(side="left", padx=5, pady=10)
        ttk.Entry(g1, textvariable=self.cen_y_var, width=6).pack(side="left", padx=5, pady=10)
        
        btn_set_cen = ttk.Button(g1, text="更新质点", command=self.update_centroid)
        btn_set_cen.pack(side="left", padx=10, pady=10)
        
        # 2. 接入端口设置
        g2 = ttk.LabelFrame(parent, text="端口接入点 (Ports) 编辑器")
        g2.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 添加新端口
        add_frame = ttk.Frame(g2)
        add_frame.pack(fill="x", padx=5, pady=5)
        
        self.p_name_var = tk.StringVar(value="N")
        self.p_x_var = tk.StringVar(value="0")
        self.p_y_var = tk.StringVar(value="30")
        
        ttk.Label(add_frame, text="标识:").grid(row=0, column=0, sticky="w")
        ttk.Entry(add_frame, textvariable=self.p_name_var, width=4).grid(row=0, column=1, sticky="w", padx=2)
        ttk.Label(add_frame, text="X:").grid(row=0, column=2, sticky="w")
        ttk.Entry(add_frame, textvariable=self.p_x_var, width=5).grid(row=0, column=3, sticky="w", padx=2)
        ttk.Label(add_frame, text="Y:").grid(row=0, column=4, sticky="w")
        ttk.Entry(add_frame, textvariable=self.p_y_var, width=5).grid(row=0, column=5, sticky="w", padx=2)
        
        btn_add_p = ttk.Button(add_frame, text="添加/更新端口", command=self.add_or_update_port)
        btn_add_p.grid(row=0, column=6, padx=5, sticky="e")
        
        # 端口列表显示与删除
        list_frame = ttk.Frame(g2)
        list_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.port_listbox = tk.Listbox(list_frame, height=6)
        self.port_listbox.pack(side="left", fill="both", expand=True)
        
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.port_listbox.yview)
        scroll.pack(side="right", fill="y")
        self.port_listbox.config(yscrollcommand=scroll.set)
        
        btn_del_p = ttk.Button(g2, text="删除选中端口", command=self.delete_selected_port)
        g2.pack_propagate(True)
        btn_del_p.pack(fill="x", padx=10, pady=5)

    # ================= 业务模型操作 =================

    def set_preset_formula(self, x, y, t_min, t_max):
        self.func_x_var.set(x)
        self.func_y_var.set(y)
        self.t_min_var.set(t_min)
        self.t_max_var.set(t_max)

    def generate_vertices_from_function(self):
        """
        根据用户输入的 X(t), Y(t) 数学表达式，在设定定义域内采样计算出离散坐标线段。
        """
        try:
            raw_x = self.func_x_var.get()
            raw_y = self.func_y_var.get()
            raw_tmin = self.t_min_var.get()
            raw_tmax = self.t_max_var.get()
            steps = int(self.t_steps_var.get())
            
            # 安全计算环境设置，引入常数 pi 以及三角函数
            safe_env = {
                "sin": math.sin, "cos": math.cos, "tan": math.tan,
                "pi": math.pi, "e": math.e, "pow": math.pow, "sqrt": math.sqrt
            }
            
            t_min = float(eval(raw_tmin, {"__builtins__": None}, safe_env))
            t_max = float(eval(raw_tmax, {"__builtins__": None}, safe_env))
            
            if steps < 3:
                raise ValueError("采样步数不能小于3。")
                
            new_vertices = []
            for i in range(steps):
                t = t_min + (t_max - t_min) * i / (steps - 1)
                safe_env["t"] = t
                
                # 计算坐标
                px = float(eval(raw_x, {"__builtins__": None}, safe_env))
                py = float(eval(raw_y, {"__builtins__": None}, safe_env))
                
                # 范围约束
                px = max(-100.0, min(100.0, px))
                py = max(-100.0, min(100.0, py))
                
                new_vertices.append([round(px, 2), round(py, 2)])
                
            self.vertices = new_vertices
            self.draw_preview()
            
        except Exception as e:
            messagebox.showerror("数学计算错误", f"计算失败。请检查公式语法及定义域配置是否正确。\n错误原因: {str(e)}")

    def update_centroid(self):
        try:
            cx = float(self.cen_x_var.get())
            cy = float(self.cen_y_var.get())
            
            self.centroid = [max(-100.0, min(100.0, cx)), max(-100.0, min(100.0, cy))]
            self.draw_preview()
        except ValueError:
            messagebox.showwarning("格式错误", "质点坐标必须为有效的数值。")

    def add_or_update_port(self):
        name = self.p_name_var.get().strip()
        if not name:
            messagebox.showwarning("警告", "端口标识不能为空。")
            return
        try:
            px = float(self.p_x_var.get())
            py = float(self.p_y_var.get())
            
            # 查重并覆盖
            existing = None
            for p in self.ports:
                if p["name"] == name:
                    existing = p
                    break
            if existing:
                existing["x"] = px
                existing["y"] = py
            else:
                self.ports.append({"name": name, "x": px, "y": py})
                
            self.refresh_port_listbox()
            self.draw_preview()
        except ValueError:
            messagebox.showwarning("格式错误", "端口坐标必须为数值。")

    def delete_selected_port(self):
        sel = self.port_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        del self.ports[idx]
        self.refresh_port_listbox()
        self.draw_preview()

    def refresh_port_listbox(self):
        self.port_listbox.delete(0, tk.END)
        for p in self.ports:
            self.port_listbox.insert(tk.END, f"{p['name']}: ({p['x']:.1f}, {p['y']:.1f})")

    # ================= 模板载入与文件交互 =================

    def on_load_preset_clicked(self):
        preset_name = self.preset_combo.get()
        self.load_shape_to_editor(preset_name)

    def _ensure_shape_metadata(self, shape_data):
        """向后兼容：为没有 bounding_box / extension 的旧格式数据自动补全"""
        if "bounding_box" not in shape_data:
            xs = [v[0] for v in shape_data["vertices"]]
            ys = [v[1] for v in shape_data["vertices"]]
            shape_data["bounding_box"] = [min(xs), min(ys), max(xs), max(ys)]
        bbox = shape_data["bounding_box"]
        for p in shape_data["ports"]:
            if "extension" not in p:
                ext_x, ext_y, direction = self._compute_port_extension(p, bbox)
                p["extension"] = {"x": ext_x, "y": ext_y, "direction": direction}

    def load_shape_to_editor(self, shape_name):
        if shape_name in self.shapes_library:
            shape = self.shapes_library[shape_name]
            self._ensure_shape_metadata(shape)
            self.vertices = [list(v) for v in shape["vertices"]]
            self.centroid = list(shape["centroid"])
            self.ports = [dict(p) for p in shape["ports"]]
            self.current_shape_name = shape_name
            self.shape_name_var.set(shape_name)
            
            # 同步输入文本框
            self.cen_x_var.set(str(self.centroid[0]))
            self.cen_y_var.set(str(self.centroid[1]))
            
            self.refresh_port_listbox()
            self.draw_preview()

    def save_current_to_library(self):
        name = self.shape_name_var.get().strip()
        if not name:
            messagebox.showwarning("命名为空", "请输入需要保存的几何体名称。")
            return

        bbox = self._compute_bounding_box()
        ports_with_ext = []
        for p in self.ports:
            ext_x, ext_y, direction = self._compute_port_extension(p, bbox)
            port_data = dict(p)
            port_data["extension"] = {"x": ext_x, "y": ext_y, "direction": direction}
            ports_with_ext.append(port_data)

        self.shapes_library[name] = {
            "vertices": [list(v) for v in self.vertices],
            "centroid": list(self.centroid),
            "bounding_box": bbox,
            "ports": ports_with_ext
        }

        # 刷新下拉列表
        self.preset_combo["values"] = list(self.shapes_library.keys())
        self.preset_combo.set(name)
        messagebox.showinfo("成功", f"几何体 '{name}' 已存入内存临时库。")

    def export_standard_file(self):
        """
        导出所有设计好的几何标准模型，保存为 JSON 配置文件（标准文件）。
        """
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("标准库文件", "*.json")]
        )
        if not file_path:
            return
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.shapes_library, f, indent=4, ensure_ascii=False)
            messagebox.showinfo("导出成功", f"标准几何模型库已成功保存至:\n{file_path}")
        except Exception as e:
            messagebox.showerror("导出失败", f"文件写入出错:\n{str(e)}")

    def import_standard_file(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("标准库文件", "*.json")]
        )
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                imported_data = json.load(f)
                
            # 校验基本数据格式
            if not isinstance(imported_data, dict):
                raise ValueError("外部标准库根节点必须为字典结构。")
                
            self.shapes_library = imported_data
            # 向后兼容：为所有导入的形状补全 bounding_box 和端口 extension
            for shape_data in self.shapes_library.values():
                self._ensure_shape_metadata(shape_data)
            self.preset_combo["values"] = list(self.shapes_library.keys())
            if list(self.shapes_library.keys()):
                first_key = list(self.shapes_library.keys())[0]
                self.preset_combo.set(first_key)
                self.load_shape_to_editor(first_key)
                
            messagebox.showinfo("载入成功", f"成功导入 {len(self.shapes_library)} 个外部标准框图模型。")
        except Exception as e:
            messagebox.showerror("解析失败", f"导入非标准格式的JSON文件:\n{str(e)}")

    # ================= 坐标换算与预览绘制 (2D 矢量渲染) =================

    def to_px(self, x, y, width, height):
        """
        将 [-100, 100] 的数学坐标系 1:1 均匀无失真投影到视口像素坐标系中。
        """
        side = min(width, height) - 40
        scale = side / 200.0  # 单个单位对应的像素步长
        
        # 视口原点置于 Canvas 绝对正中心
        ox = width / 2
        oy = height / 2
        
        px = ox + (x * scale)
        py = oy - (y * scale)  # Y轴向上递增
        return px, py

    def _port_direction(self, port_name):
        """从端口名提取方向首字母 N/S/E/W"""
        if not port_name:
            return 'N'
        return port_name[0].upper()

    def _compute_bounding_box(self):
        """从当前顶点列表计算延申区域（外包矩形每方向+5）[min_x, min_y, max_x, max_y]"""
        if not self.vertices:
            return [-65, -35, 65, 35]
        xs = [v[0] for v in self.vertices]
        ys = [v[1] for v in self.vertices]
        return [min(xs) - 5, min(ys) - 5, max(xs) + 5, max(ys) + 5]

    def _compute_port_extension(self, port, bbox, margin=5):
        """计算端口引出线的终点坐标（在延申区域边界外侧 margin 处）

        方案B：向最近的外包矩形边的垂直方向延伸。
        返回 (ext_x, ext_y, direction)
        """
        px, py = port['x'], port['y']
        min_x, min_y, max_x, max_y = bbox

        # 到四条边的距离
        d_top = max_y - py
        d_bottom = py - min_y
        d_right = max_x - px
        d_left = px - min_x

        # 找最近边，向外垂直延伸 margin
        edges = [
            (d_top, px, max_y + margin, 'N'),
            (d_bottom, px, min_y - margin, 'S'),
            (d_right, max_x + margin, py, 'E'),
            (d_left, min_x - margin, py, 'W'),
        ]
        _, ext_x, ext_y, direction = min(edges, key=lambda e: e[0])

        return ext_x, ext_y, direction

    def draw_preview(self):
        canvas = self.canvas
        canvas.delete("all")
        
        W = canvas.winfo_width()
        H = canvas.winfo_height()
        if W <= 1 or H <= 1:
            W, H = 500, 500 # 初始渲染占位
            
        # 1. 绘制网格辅助虚线 (20个刻度一个格子)
        for i in range(-100, 101, 20):
            # 垂直线
            px_v, _ = self.to_px(i, 0, W, H)
            grid_color = "#EBF0F2" if i != 0 else "#CFD8DC"
            grid_width = 1 if i != 0 else 2
            canvas.create_line(px_v, 0, px_v, H, fill=grid_color, width=grid_width)
            if i != 0:
                canvas.create_text(px_v, H - 15, text=str(i), fill="#90A4AE", font=("Arial", 7))
            
            # 水平线
            _, py_h = self.to_px(0, i, W, H)
            canvas.create_line(0, py_h, W, py_h, fill=grid_color, width=grid_width)
            if i != 0:
                canvas.create_text(15, py_h, text=str(i), fill="#90A4AE", font=("Arial", 7))
                
        # 2. 绘制多边形外廓 (线段闭合)
        if len(self.vertices) >= 2:
            px_path = []
            for vx, vy in self.vertices:
                px_path.extend(self.to_px(vx, vy, W, H))
                
            # 闭合轮廓
            px_path.extend(self.to_px(self.vertices[0][0], self.vertices[0][1], W, H))
            canvas.create_line(px_path, fill="#263238", width=3, smooth=False)
            
            # 画出每一个多边形的离散顶点圆圈，方便调试微调
            for vx, vy in self.vertices:
                px, py = self.to_px(vx, vy, W, H)
                canvas.create_oval(px-3, py-3, px+3, py+3, fill="#FFFFFF", outline="#37474F", width=1)

        # 2.5 绘制延申区域（外包矩形虚线框）
        bbox = self._compute_bounding_box()
        bx1, by1 = self.to_px(bbox[0], bbox[1], W, H)
        bx2, by2 = self.to_px(bbox[2], bbox[3], W, H)
        canvas.create_rectangle(bx1, by1, bx2, by2, outline="#90A4AE", dash=(4, 4), width=1)

        # 3. 绘制手动设置的质点 (红十字标识)
        cx, cy = self.to_px(self.centroid[0], self.centroid[1], W, H)
        canvas.create_line(cx - 10, cy, cx + 10, cy, fill="#D32F2F", width=2)
        canvas.create_line(cx, cy - 10, cx, cy + 10, fill="#D32F2F", width=2)
        canvas.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill="#D32F2F", outline="")
        canvas.create_text(cx + 12, cy - 8, text="质心", fill="#D32F2F", font=("Microsoft YaHei", 8, "bold"))

        # 4. 绘制接入端口点 (蓝点及标注)
        for p in self.ports:
            px, py = self.to_px(p["x"], p["y"], W, H)
            canvas.create_oval(px-5, py-5, px+5, py+5, fill="#1E88E5", outline="#0D47A1", width=1.5)
            # 绘制方向指示
            canvas.create_text(px, py-12, text=p["name"], fill="#0D47A1", font=("Arial", 8, "bold"))

        # 4.5 绘制端口引出线（虚线延伸至延申区域外）
        for p in self.ports:
            px, py = self.to_px(p["x"], p["y"], W, H)
            ext_x, ext_y, _ = self._compute_port_extension(p, bbox)
            epx, epy = self.to_px(ext_x, ext_y, W, H)
            canvas.create_line(px, py, epx, epy, fill="#B0BEC5", dash=(2, 4), width=1)
            canvas.create_oval(epx-2, epy-2, epx+2, epy+2, fill="#B0BEC5", outline="")

        # 5. 同步刷新导出渲染预览
        if hasattr(self, 'export_canvas') and self.export_canvas.winfo_exists():
            self.draw_export_preview()

    # ================= 导出与渲染 (SVG / PNG / PDF) =================

    def setup_export_tab(self, parent):
        """导出与渲染 Tab：预览并导出 SVG / PNG / PDF 三种格式"""
        # --- 控制区 ---
        ctrl = ttk.LabelFrame(parent, text="导出格式与参数")
        ctrl.pack(fill="x", padx=10, pady=10)

        row = ttk.Frame(ctrl)
        row.pack(fill="x", padx=10, pady=8)

        ttk.Label(row, text="缩放系数:").pack(side="left")
        self.export_scale_var = tk.StringVar(value="4")
        ttk.Spinbox(row, from_=1, to=10, textvariable=self.export_scale_var, width=4).pack(side="left", padx=5)
        ttk.Label(row, text="(PNG/PDF: 每坐标单位像素数,  SVG: 视图缩放比)").pack(side="left", padx=5)

        btn_row = ttk.Frame(ctrl)
        btn_row.pack(fill="x", padx=10, pady=(0, 10))

        ttk.Button(btn_row, text="导出 SVG (矢量)", command=lambda: self.export_shape("svg")).pack(
            side="left", expand=True, fill="x", padx=3)

        png_btn = ttk.Button(btn_row, text="导出 PNG (位图)", command=lambda: self.export_shape("png"))
        png_btn.pack(side="left", expand=True, fill="x", padx=3)
        if not HAS_PIL:
            png_btn.configure(state="disabled")

        pdf_btn = ttk.Button(btn_row, text="导出 PDF (文档)", command=lambda: self.export_shape("pdf"))
        pdf_btn.pack(side="left", expand=True, fill="x", padx=3)
        if not HAS_PIL:
            pdf_btn.configure(state="disabled")

        if not HAS_PIL:
            ttk.Label(ctrl, text="⚠ Pillow 未安装，PNG / PDF 导出不可用。请运行: pip install Pillow",
                      foreground="#E65100").pack(padx=10, pady=(0, 8))

        # --- 预览区 ---
        preview_frame = ttk.LabelFrame(parent, text="渲染预览（白底无网格，模拟实际导出效果）")
        preview_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.export_canvas = tk.Canvas(preview_frame, bg="#FFFFFF", highlightthickness=0)
        self.export_canvas.pack(fill="both", expand=True, padx=5, pady=5)
        self.export_canvas.bind("<Configure>", lambda e: self.draw_export_preview())

    def draw_export_preview(self):
        """在导出 Tab 中绘制干净的白底预览，模拟导出文件外观"""
        canvas = self.export_canvas
        if not canvas.winfo_exists():
            return
        canvas.delete("all")

        W = canvas.winfo_width()
        H = canvas.winfo_height()
        if W <= 1 or H <= 1:
            return

        side = min(W, H) - 40
        scale = side / 200.0
        ox, oy = W / 2, H / 2

        def to_px(x, y):
            return ox + x * scale, oy - y * scale

        # 形状多边形（带浅底色填充）
        if len(self.vertices) >= 2:
            pts = []
            for vx, vy in self.vertices:
                pts.extend(to_px(vx, vy))
            pts.extend(to_px(self.vertices[0][0], self.vertices[0][1]))
            canvas.create_polygon(pts, fill="#F8FAFC", outline="#263238", width=2, joinstyle="miter")

            # 顶点小圆点
            for vx, vy in self.vertices:
                px, py = to_px(vx, vy)
                canvas.create_oval(px - 2, py - 2, px + 2, py + 2, fill="#FFFFFF", outline="#37474F")

        # 延申区域（外包矩形虚线框）
        bbox = self._compute_bounding_box()
        bx1, by1 = to_px(bbox[0], bbox[1])
        bx2, by2 = to_px(bbox[2], bbox[3])
        canvas.create_rectangle(bx1, by1, bx2, by2, outline="#90A4AE", dash=(4, 4), width=1)

        # 质心红十字
        cx, cy = to_px(self.centroid[0], self.centroid[1])
        canvas.create_line(cx - 8, cy, cx + 8, cy, fill="#D32F2F", width=2)
        canvas.create_line(cx, cy - 8, cx, cy + 8, fill="#D32F2F", width=2)
        canvas.create_text(cx + 12, cy - 8, text="质心", fill="#D32F2F", font=("Microsoft YaHei", 8, "bold"))

        # 端口蓝色圆点及标注
        for p in self.ports:
            px, py = to_px(p["x"], p["y"])
            canvas.create_oval(px - 5, py - 5, px + 5, py + 5, fill="#1E88E5", outline="#0D47A1", width=1.5)
            canvas.create_text(px, py - 12, text=p["name"], fill="#0D47A1", font=("Arial", 8, "bold"))

        # 端口引出线（虚线延伸至延申区域外）
        for p in self.ports:
            px, py = to_px(p["x"], p["y"])
            ext_x, ext_y, _ = self._compute_port_extension(p, bbox)
            epx, epy = to_px(ext_x, ext_y)
            canvas.create_line(px, py, epx, epy, fill="#B0BEC5", dash=(2, 4), width=1)
            canvas.create_oval(epx - 2, epy - 2, epx + 2, epy + 2, fill="#B0BEC5", outline="")

    def export_shape(self, fmt):
        """统一导出入口，根据格式派发到对应渲染方法"""
        ext_desc = {"svg": "SVG 矢量图", "png": "PNG 位图", "pdf": "PDF 文档"}
        desc = ext_desc.get(fmt, fmt.upper())

        filepath = filedialog.asksaveasfilename(
            defaultextension=f".{fmt}",
            filetypes=[(f"{desc} (*.{fmt})", f"*.{fmt}")]
        )
        if not filepath:
            return

        try:
            if fmt == "svg":
                self._render_to_svg(filepath)
            elif fmt == "png":
                self._render_to_png(filepath)
            elif fmt == "pdf":
                self._render_to_pdf(filepath)
            messagebox.showinfo("导出成功", f"形状已成功导出至:\n{filepath}")
        except Exception as e:
            messagebox.showerror("导出失败", f"渲染过程出错:\n{str(e)}")

    def _render_to_svg(self, filepath):
        """使用 svgwrite 导出矢量 SVG 文件（含延申区域 + 引出线）"""
        view_scale = int(self.export_scale_var.get())
        size = 200 * view_scale
        dwg = svgwrite.Drawing(filepath, size=(f"{size}px", f"{size}px"))
        dwg.viewbox(-110, -110, 220, 220)

        # 白色背景
        dwg.add(dwg.rect(insert=(-110, -110), size=(220, 220), fill='white'))

        bbox = self._compute_bounding_box()
        # Y 翻转辅助
        def fy(y):
            return -y

        # 延申区域（外包矩形虚线框）
        dwg.add(dwg.rect(
            insert=(bbox[0], fy(bbox[3])),
            size=(bbox[2] - bbox[0], bbox[3] - bbox[1]),
            fill='none', stroke='#90A4AE', stroke_width=1, stroke_dasharray='4,4'))

        # 形状多边形（Y 翻转：数学坐标 Y 向上 → SVG Y 向下）
        if len(self.vertices) >= 2:
            pts = [(v[0], fy(v[1])) for v in self.vertices]
            dwg.add(dwg.polygon(pts, fill='#F8FAFC', stroke='#263238', stroke_width=2,
                                stroke_linejoin='miter'))
            # 顶点标记
            for vx, vy in self.vertices:
                dwg.add(dwg.circle((vx, fy(vy)), r=2, fill='white', stroke='#37474F', stroke_width=0.5))

        # 质心红十字
        cx, cy = self.centroid
        dwg.add(dwg.line((cx - 8, fy(cy)), (cx + 8, fy(cy)), stroke='#D32F2F', stroke_width=2))
        dwg.add(dwg.line((cx, fy(cy) - 8), (cx, fy(cy) + 8), stroke='#D32F2F', stroke_width=2))

        # 端口引出线（虚线延伸至延申区域外）
        for p in self.ports:
            ext_x, ext_y, _ = self._compute_port_extension(p, bbox)
            dwg.add(dwg.line((p['x'], fy(p['y'])), (ext_x, fy(ext_y)),
                            stroke='#B0BEC5', stroke_width=1, stroke_dasharray='2,4'))

        # 端口蓝点 + 标签（半径跟随视图缩放：r=2 在 viewBox 坐标中）
        port_r = 2
        for p in self.ports:
            dwg.add(dwg.circle((p['x'], fy(p['y'])), r=port_r, fill='#1E88E5', stroke='#0D47A1', stroke_width=1))
            dwg.add(dwg.text(p['name'], x=p['x'], y=fy(p['y']) - port_r - 6,
                            fill='#0D47A1', font_size=9, font_family='Arial',
                            text_anchor='middle', font_weight='bold'))

        dwg.save()

    def _render_to_png(self, filepath):
        """使用 PIL 导出高分辨率 PNG 位图"""
        if not HAS_PIL:
            raise ImportError("Pillow 未安装，无法导出 PNG。请运行: pip install Pillow")
        user_scale = int(self.export_scale_var.get())
        bbox = self._compute_bounding_box()
        shape_w = bbox[2] - bbox[0]
        shape_h = bbox[3] - bbox[1]
        if shape_w <= 0 or shape_h <= 0:
            shape_w = shape_h = 200
        scale = user_scale  # 每数学单位对应的像素数
        padding = int(10 * scale)
        img_w = int(shape_w * scale + 2 * padding)
        img_h = int(shape_h * scale + 2 * padding)
        img = self._draw_pil_image(img_w, img_h, bbox, scale, padding)
        img.save(filepath, 'PNG')

    def _render_to_pdf(self, filepath):
        """导出 A4 PDF（300dpi 高分辨率位图嵌入，图形等比适配页边距）"""
        if not HAS_PIL:
            raise ImportError("Pillow 未安装，无法导出 PDF。请运行: pip install Pillow")

        dpi = 300
        a4_w_mm, a4_h_mm = 210, 297
        margin_mm = 15

        img_w = int(a4_w_mm / 25.4 * dpi)   # ~2480
        img_h = int(a4_h_mm / 25.4 * dpi)   # ~3508
        margin = int(margin_mm / 25.4 * dpi)  # ~177

        avail_w = img_w - 2 * margin
        avail_h = img_h - 2 * margin

        bbox = self._compute_bounding_box()
        shape_w = bbox[2] - bbox[0]
        shape_h = bbox[3] - bbox[1]
        if shape_w <= 0 or shape_h <= 0:
            shape_w = shape_h = 200

        # 等比缩放适配 A4 可用区域
        fit_scale = min(avail_w / shape_w, avail_h / shape_h)
        user_scale = int(self.export_scale_var.get())
        scale = fit_scale * (user_scale / 4.0)

        # 居中偏移
        offset_x = margin + (avail_w - shape_w * scale) / 2 - bbox[0] * scale
        offset_y = margin + (avail_h - shape_h * scale) / 2 + bbox[3] * scale

        def to_px(x, y):
            px = offset_x + x * scale
            py = offset_y - y * scale
            return int(px), int(py)

        img = Image.new('RGB', (img_w, img_h), 'white')
        draw = ImageDraw.Draw(img)

        # 字体
        font_size = max(8, int(9 * scale))
        try:
            font = ImageFont.truetype("arial.ttf", size=font_size)
        except Exception:
            font = ImageFont.load_default()

        self._draw_shape_on_pil(draw, to_px, bbox, scale, font)
        img.save(filepath, 'PDF', resolution=dpi)

    def _draw_pil_image(self, img_w, img_h, bbox, scale, padding):
        """创建 PIL Image 并绘制形状（供 PNG 使用）"""

        def to_px(x, y):
            px = padding + (x - bbox[0]) * scale
            py = padding + (bbox[3] - y) * scale
            return int(px), int(py)

        img = Image.new('RGB', (img_w, img_h), 'white')
        draw = ImageDraw.Draw(img)

        font_size = max(8, int(9 * scale))
        try:
            font = ImageFont.truetype("arial.ttf", size=font_size)
        except Exception:
            font = ImageFont.load_default()

        self._draw_shape_on_pil(draw, to_px, bbox, scale, font)
        return img

    def _draw_shape_on_pil(self, draw, to_px, bbox, scale, font):
        """在 PIL draw 对象上绘制形状、延申区域、端口引出线（共用核心逻辑）"""

        # 延申区域（外包矩形，细灰线）
        bx1, by1 = to_px(bbox[0], bbox[1])
        bx2, by2 = to_px(bbox[2], bbox[3])
        # 确保坐标顺序正确（Y 翻转后 by1 可能 > by2，PIL 要求 y0 ≤ y1）
        if bx1 > bx2:
            bx1, bx2 = bx2, bx1
        if by1 > by2:
            by1, by2 = by2, by1
        line_w = max(1, int(1 * scale))
        draw.rectangle([bx1, by1, bx2, by2], outline='#90A4AE', width=line_w)

        # 形状多边形（带填充）
        if len(self.vertices) >= 2:
            pts = [to_px(v[0], v[1]) for v in self.vertices]
            line_w = max(1, int(2 * scale))
            draw.polygon(pts, fill='#F8FAFC', outline='#263238', width=line_w)

        # 质心红十字
        cx, cy = to_px(self.centroid[0], self.centroid[1])
        lw = max(1, int(2 * scale))
        cross_len = max(4, int(8 * scale))
        draw.line([(cx - cross_len, cy), (cx + cross_len, cy)], fill='#D32F2F', width=lw)
        draw.line([(cx, cy - cross_len), (cx, cy + cross_len)], fill='#D32F2F', width=lw)

        # 端口引出线（灰线）
        ext_lw = max(1, int(1 * scale))
        for p in self.ports:
            px, py = to_px(p['x'], p['y'])
            ext_x, ext_y, _ = self._compute_port_extension(p, bbox)
            epx, epy = to_px(ext_x, ext_y)
            draw.line([(px, py), (epx, epy)], fill='#B0BEC5', width=ext_lw)

        # 端口蓝点（半径随缩放比例变化）+ 标签
        port_r = max(1, int(1.5 * scale))
        port_lw = max(1, int(1 * scale))
        for p in self.ports:
            px, py = to_px(p['x'], p['y'])
            draw.ellipse([px - port_r, py - port_r, px + port_r, py + port_r],
                        fill='#1E88E5', outline='#0D47A1', width=port_lw)
            # 标签居中于端口上方
            label = p['name']
            try:
                tbbox = draw.textbbox((0, 0), label, font=font)
                tw = tbbox[2] - tbbox[0]
            except AttributeError:
                tw = len(label) * font.size * 0.6
            draw.text((px - tw / 2, py - port_r - font.size - 2), label, fill='#0D47A1', font=font)


if __name__ == "__main__":
    root = tk.Tk()
    app = ShapeDesignerApp(root)
    root.update()
    app.draw_preview()
    root.mainloop()