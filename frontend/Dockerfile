# ============================================
# Stage 1: Builder - Instalar dependencias y build
# ============================================
FROM node:18-alpine as builder

WORKDIR /app

# Copiar archivos de dependencias
COPY package*.json ./

# Instalar todas las dependencias (incluyendo devDependencies)
RUN npm install

# Copiar código fuente
COPY . .

# Build de la aplicación (si fuera producción)
# RUN npm run build

# ============================================
# Stage 2: Development - Runtime con hot reload
# ============================================
FROM node:18-alpine as development

WORKDIR /app

# Copiar package files
COPY package*.json ./

# Instalar todas las dependencias (incluyendo devDependencies para hot reload)
RUN npm install

# Copiar código de la aplicación
COPY . .

# Exponer puerto
EXPOSE 5173

# Comando para desarrollo (hot reload)
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# ============================================
# Stage 3: Production - Servir archivos estáticos
# ============================================
FROM node:18-alpine as production

WORKDIR /app

# Copiar package files
COPY package*.json ./

# Instalar solo dependencias de producción
RUN npm install --only=production

# Copiar archivos build desde builder
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/index.html ./index.html

# Instalar servidor estático ligero
RUN npm install -g serve

# Crear usuario no-root
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nextjs -u 1001

USER nextjs

# Exponer puerto
EXPOSE 3000

# Servir archivos estáticos
CMD ["serve", "-s", "dist", "-l", "3000"]
