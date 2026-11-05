export interface GraphNode {
    id: string;
    label: string;
    type: string;
    x?: number;
    y?: number;
    vx?: number;
    vy?: number;
}

export interface GraphEdge {
    source: string | GraphNode;
    target: string | GraphNode;
    relation?: string;
    type?: string;
}

export class GraphVisualizer {
    private canvas: HTMLCanvasElement;
    private ctx: CanvasRenderingContext2D;
    private nodes: GraphNode[] = [];
    private edges: GraphEdge[] = [];
    private nodeMap: Map<string, GraphNode> = new Map();
    
    // Viewport
    private scale: number = 1.0;
    private panX: number = 0;
    private panY: number = 0;
    
    // Physics parameters
    private repulsion: number = 50000;
    private stiffness: number = 0.05;
    private damping: number = 0.85;
    private restLength: number = 150;
    private gravity: number = 0.02;

    // Keep the whole graph in view until the user pans or zooms by hand
    private autoFit: boolean = true;

    // Interaction state
    private isDragging: boolean = false;
    private isPanning: boolean = false;
    private draggedNode: GraphNode | null = null;
    private hoveredNode: GraphNode | null = null;
    private lastMouseX: number = 0;
    private lastMouseY: number = 0;
    
    // Callbacks
    private onNodeClick?: (node: GraphNode) => void;
    
    // Rendering state
    private animationFrameId: number | null = null;

    constructor(canvas: HTMLCanvasElement, onNodeClick?: (node: GraphNode) => void) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d')!;
        this.onNodeClick = onNodeClick;
        
        // Initial setup
        this.resize();
        this.panX = this.canvas.width / 2;
        this.panY = this.canvas.height / 2;
        
        this.setupEventListeners();
        this.startLoop();
    }

    public setData(nodes: GraphNode[], edges: GraphEdge[]) {
        this.nodes = [];
        this.edges = [];
        this.nodeMap.clear();
        this.autoFit = true;

        // Spawn in a circle to prevent identical origins
        const cx = 0;
        const cy = 0;
        const radius = 100;

        nodes.forEach((n, i) => {
            const angle = (i / nodes.length) * 2 * Math.PI;
            const node: GraphNode = {
                ...n,
                x: cx + Math.cos(angle) * radius,
                y: cy + Math.sin(angle) * radius,
                vx: 0,
                vy: 0
            };
            this.nodes.push(node);
            this.nodeMap.set(node.id, node);
        });

        edges.forEach(e => {
            const sourceId = typeof e.source === 'string' ? e.source : e.source.id;
            const targetId = typeof e.target === 'string' ? e.target : e.target.id;
            
            const source = this.nodeMap.get(sourceId);
            const target = this.nodeMap.get(targetId);

            if (source && target) {
                this.edges.push({
                    source,
                    target,
                    relation: e.relation || e.type || 'connected'
                });
            }
        });

        // Lay the graph out once, up front, so it appears still instead of jittering into place.
        const steps = 300;
        for (let i = 0; i < steps; i++) this._stepPhysics(1 - i / steps);
    }

    public resize() {
        const rect = this.canvas.parentElement?.getBoundingClientRect();
        if (rect) {
            this.canvas.width = rect.width;
            this.canvas.height = rect.height;
        }
        this.autoFit = true;
    }

    private setupEventListeners() {
        this.canvas.addEventListener('mousedown', this.onMouseDown.bind(this));
        this.canvas.addEventListener('mousemove', this.onMouseMove.bind(this));
        this.canvas.addEventListener('mouseup', this.onMouseUp.bind(this));
        this.canvas.addEventListener('mouseleave', this.onMouseUp.bind(this));
        this.canvas.addEventListener('wheel', this.onWheel.bind(this), { passive: false });
        window.addEventListener('resize', () => this.resize());
    }

    private _getCanvasCoords(screenX: number, screenY: number) {
        const rect = this.canvas.getBoundingClientRect();
        const x = (screenX - rect.left - this.panX) / this.scale;
        const y = (screenY - rect.top - this.panY) / this.scale;
        return { x, y };
    }

    private onMouseDown(e: MouseEvent) {
        const coords = this._getCanvasCoords(e.clientX, e.clientY);
        this.lastMouseX = e.clientX;
        this.lastMouseY = e.clientY;

        // Find clicked node
        for (let i = this.nodes.length - 1; i >= 0; i--) {
            const n = this.nodes[i];
            const dx = coords.x - n.x!;
            const dy = coords.y - n.y!;
            if (dx * dx + dy * dy < 400) { // Radius 20^2
                this.draggedNode = n;
                this.isDragging = true;
                if (this.onNodeClick) this.onNodeClick(n);
                return;
            }
        }

        // Background click -> pan
        this.isPanning = true;
    }

    private onMouseMove(e: MouseEvent) {
        const dx = e.clientX - this.lastMouseX;
        const dy = e.clientY - this.lastMouseY;
        
        if (this.isDragging && this.draggedNode) {
            this.autoFit = false;
            this.draggedNode.x! += dx / this.scale;
            this.draggedNode.y! += dy / this.scale;
        } else if (this.isPanning) {
            this.autoFit = false;
            this.panX += dx;
            this.panY += dy;
        } else {
            // Hover check
            const coords = this._getCanvasCoords(e.clientX, e.clientY);
            this.hoveredNode = null;
            for (let i = this.nodes.length - 1; i >= 0; i--) {
                const n = this.nodes[i];
                const nx = coords.x - n.x!;
                const ny = coords.y - n.y!;
                if (nx * nx + ny * ny < 400) {
                    this.hoveredNode = n;
                    this.canvas.style.cursor = 'pointer';
                    break;
                }
            }
            if (!this.hoveredNode) {
                this.canvas.style.cursor = 'default';
            }
        }
        
        this.lastMouseX = e.clientX;
        this.lastMouseY = e.clientY;
    }

    private onMouseUp() {
        this.isDragging = false;
        this.isPanning = false;
        this.draggedNode = null;
    }

    private onWheel(e: WheelEvent) {
        e.preventDefault();
        this.autoFit = false;

        const zoomIntensity = 0.1;
        const zoom = Math.exp(e.deltaY < 0 ? zoomIntensity : -zoomIntensity);
        
        const rect = this.canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        // Scale towards mouse
        this.panX = mouseX - (mouseX - this.panX) * zoom;
        this.panY = mouseY - (mouseY - this.panY) * zoom;
        this.scale *= zoom;
    }

    // `cooling` falls from 1 to 0 across the layout, so movement shrinks until the nodes stop.
    private _stepPhysics(cooling: number) {
        if (this.nodes.length === 0) return;

        // 1. Repulsion (Coulomb)
        for (let i = 0; i < this.nodes.length; i++) {
            const n1 = this.nodes[i];
            for (let j = i + 1; j < this.nodes.length; j++) {
                const n2 = this.nodes[j];
                const dx = n2.x! - n1.x!;
                const dy = n2.y! - n1.y!;
                const distSq = dx * dx + dy * dy || 1;
                
                if (distSq < 250000) { // ~500px radius
                    const dist = Math.sqrt(distSq);
                    const force = this.repulsion / distSq;
                    const fx = (dx / dist) * force;
                    const fy = (dy / dist) * force;
                    
                    n1.vx! -= fx;
                    n1.vy! -= fy;
                    n2.vx! += fx;
                    n2.vy! += fy;
                }
            }
        }

        // 2. Attraction (Hooke's Law via Edges)
        for (const e of this.edges) {
            const source = e.source as GraphNode;
            const target = e.target as GraphNode;
            
            const dx = target.x! - source.x!;
            const dy = target.y! - source.y!;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            
            const force = (dist - this.restLength) * this.stiffness;
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;
            
            source.vx! += fx;
            source.vy! += fy;
            target.vx! -= fx;
            target.vy! -= fy;
        }

        // 3. Center Gravity & Velocity Update
        for (const n of this.nodes) {
            // Gravity towards 0,0
            n.vx! -= n.x! * this.gravity;
            n.vy! -= n.y! * this.gravity;

            // Damping & Integration
            n.vx! *= this.damping;
            n.vy! *= this.damping;
            n.x! += n.vx! * cooling;
            n.y! += n.vy! * cooling;
        }
    }

    private _getIconForType(type: string) {
        if (!type) return '⚪';
        const t = type.toLowerCase();
        if (t.includes('person') || t.includes('employee')) return '👤';
        if (t.includes('email') || t.includes('message')) return '✉️';
        if (t.includes('topic') || t.includes('theme')) return '🏷️';
        if (t.includes('chunk')) return '📄';
        if (t.includes('entity')) return '🔶';
        return '⚪';
    }

    private _fitToView() {
        if (!this.autoFit || this.nodes.length === 0) return;
        const { width, height } = this.canvas;
        const xs = this.nodes.map(n => n.x!);
        const ys = this.nodes.map(n => n.y!);
        const [minX, maxX, minY, maxY] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
        // Screen-pixel margins leave room for the node circle and its label.
        this.scale = Math.min(1, (width - 140) / (maxX - minX || 1), (height - 100) / (maxY - minY || 1));
        this.panX = width / 2 - ((minX + maxX) / 2) * this.scale;
        this.panY = height / 2 - ((minY + maxY) / 2) * this.scale;
    }

    private _render() {
        const { width, height } = this.canvas;
        // Opaque, so page-darkening extensions cannot hide the dark labels.
        this.ctx.fillStyle = '#fafaf8';
        this.ctx.fillRect(0, 0, width, height);
        this._fitToView();

        this.ctx.save();
        this.ctx.translate(this.panX, this.panY);
        this.ctx.scale(this.scale, this.scale);

        // Render Edges
        this.ctx.lineWidth = 1;
        for (const e of this.edges) {
            const source = e.source as GraphNode;
            const target = e.target as GraphNode;
            
            // Highlight check
            const isActive = this.hoveredNode === source || this.hoveredNode === target;
            
            this.ctx.strokeStyle = isActive ? '#243f8f' : '#c4cad0';
            this.ctx.globalAlpha = (this.hoveredNode && !isActive) ? 0.1 : 1.0;
            
            this.ctx.beginPath();
            this.ctx.moveTo(source.x!, source.y!);
            this.ctx.lineTo(target.x!, target.y!);
            this.ctx.stroke();

            // Edge Label (optional, can be disabled if too cluttered)
            if (isActive && e.relation) {
                const midX = (source.x! + target.x!) / 2;
                const midY = (source.y! + target.y!) / 2;
                
                this.ctx.font = '10px monospace';
                const textWidth = this.ctx.measureText(e.relation).width;
                
                this.ctx.fillStyle = '#eceef0';
                this.ctx.fillRect(midX - textWidth/2 - 2, midY - 6, textWidth + 4, 12);
                
                this.ctx.fillStyle = '#5b646d';
                this.ctx.textAlign = 'center';
                this.ctx.textBaseline = 'middle';
                this.ctx.fillText(e.relation, midX, midY);
            }
        }

        // Render Nodes
        for (const n of this.nodes) {
            const isActive = this.hoveredNode === n || (this.hoveredNode && this.edges.some(e => 
                (e.source === n && e.target === this.hoveredNode) || 
                (e.target === n && e.source === this.hoveredNode)
            ));

            this.ctx.globalAlpha = (this.hoveredNode && !isActive) ? 0.1 : 1.0;
            
            // Glow
            if (isActive) {
                this.ctx.beginPath();
                this.ctx.arc(n.x!, n.y!, 24, 0, Math.PI * 2);
                this.ctx.fillStyle = 'rgba(36, 63, 143, 0.18)';
                this.ctx.fill();
            }

            // Circle Body
            this.ctx.beginPath();
            this.ctx.arc(n.x!, n.y!, 16, 0, Math.PI * 2);
            this.ctx.fillStyle = '#fafaf8';
            this.ctx.strokeStyle = isActive ? '#243f8f' : '#76808a';
            this.ctx.lineWidth = 2;
            this.ctx.fill();
            this.ctx.stroke();

            // Icon
            this.ctx.font = '16px Arial';
            this.ctx.textAlign = 'center';
            this.ctx.textBaseline = 'middle';
            this.ctx.fillText(this._getIconForType(n.type), n.x!, n.y!);

            // Label: same on-screen size at any zoom, shortened (the full text is in the details card)
            const label = n.label || n.id;
            this.ctx.font = `${11 / this.scale}px monospace`;
            this.ctx.fillStyle = '#14181c';
            this.ctx.fillText(label.length > 18 ? `${label.slice(0, 17)}…` : label, n.x!, n.y! + 16 + 10 / this.scale);
        }

        this.ctx.restore();
    }

    private loop() {
        this._render();
        this.animationFrameId = requestAnimationFrame(() => this.loop());
    }

    public startLoop() {
        if (!this.animationFrameId) {
            this.loop();
        }
    }

    public stopLoop() {
        if (this.animationFrameId) {
            cancelAnimationFrame(this.animationFrameId);
            this.animationFrameId = null;
        }
    }

    public destroy() {
        this.stopLoop();
        this.canvas.removeEventListener('mousedown', this.onMouseDown);
        this.canvas.removeEventListener('mousemove', this.onMouseMove);
        this.canvas.removeEventListener('mouseup', this.onMouseUp);
        this.canvas.removeEventListener('mouseleave', this.onMouseUp);
        this.canvas.removeEventListener('wheel', this.onWheel);
    }
}
