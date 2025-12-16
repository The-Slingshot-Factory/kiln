#include "scene_renderer.h"

#define GL_GLEXT_PROTOTYPES
#include <GLFW/glfw3.h>

#include <vector>
#include <functional>
#include <cstdio>
#include <cmath>
#include <limits>

// ═══════════════════════════════════════════════════════════════════════════
// Shader Sources
// ═══════════════════════════════════════════════════════════════════════════

static const char* LINE_VERTEX_SHADER = R"(
#version 330 core
layout (location = 0) in vec3 aPos;
layout (location = 1) in vec3 aColor;

out vec3 vColor;
uniform mat4 uViewProjection;

void main()
{
    gl_Position = uViewProjection * vec4(aPos, 1.0);
    vColor = aColor;
}
)";

static const char* LINE_FRAGMENT_SHADER = R"(
#version 330 core
in vec3 vColor;
out vec4 FragColor;

void main()
{
    FragColor = vec4(vColor, 1.0);
}
)";

static const char* MESH_VERTEX_SHADER = R"(
#version 330 core
layout (location = 0) in vec3 aPos;

uniform mat4 uViewProjection;

void main()
{
    gl_Position = uViewProjection * vec4(aPos, 1.0);
}
)";

static const char* MESH_FRAGMENT_SHADER = R"(
#version 330 core
out vec4 FragColor;

uniform vec3 uColor;

void main()
{
    FragColor = vec4(uColor, 1.0);
}
)";

// Outline shader - renders wireframe with stipple pattern
static const char* OUTLINE_VERTEX_SHADER = R"(
#version 330 core
layout (location = 0) in vec3 aPos;

uniform mat4 uViewProjection;

void main()
{
    gl_Position = uViewProjection * vec4(aPos, 1.0);
}
)";

static const char* OUTLINE_FRAGMENT_SHADER = R"(
#version 330 core
out vec4 FragColor;

uniform vec3 uColor;

void main()
{
    FragColor = vec4(uColor, 1.0);
}
)";

// ═══════════════════════════════════════════════════════════════════════════
// SceneRenderer Implementation
// ═══════════════════════════════════════════════════════════════════════════

SceneRenderer::SceneRenderer() = default;

SceneRenderer::~SceneRenderer()
{
    cleanup();
}

void SceneRenderer::init(int width, int height)
{
    createShaders();
    createGridMesh();
    createAxesMesh();
    createFramebuffer(width, height);
}

void SceneRenderer::resize(int width, int height)
{
    if (width <= 0 || height <= 0) return;
    if (width == viewportWidth && height == viewportHeight) return;
    
    // Recreate framebuffer with new size
    if (fbo != 0)
    {
        glDeleteFramebuffers(1, &fbo);
        glDeleteTextures(1, &colorTexture);
        glDeleteRenderbuffers(1, &depthRenderbuffer);
        fbo = 0;
        colorTexture = 0;
        depthRenderbuffer = 0;
    }
    
    createFramebuffer(width, height);
}

void SceneRenderer::setScene(const Scene* scene)
{
    // Clear existing scene meshes
    clearScene();
    
    currentScene = scene;
    hoveredNode = nullptr;
    
    if (!scene || !scene->root)
    {
        return;
    }
    
    // Recursively collect and upload all mesh nodes
    std::function<void(SceneNode*)> processMeshes = [&](SceneNode* node)
    {
        if (node->type == PrimType::Mesh && node->meshData && !node->meshData->vertices.empty())
        {
            GPUMesh gpuMesh;
            gpuMesh.color = node->meshData->displayColor;
            gpuMesh.indexCount = static_cast<int>(node->meshData->indices.size());
            gpuMesh.sceneNode = node;  // Store reference to scene node
            
            // Create VAO
            glGenVertexArrays(1, &gpuMesh.vao);
            glGenBuffers(1, &gpuMesh.vbo);
            glGenBuffers(1, &gpuMesh.ebo);
            
            glBindVertexArray(gpuMesh.vao);
            
            // Upload vertices
            glBindBuffer(GL_ARRAY_BUFFER, gpuMesh.vbo);
            glBufferData(GL_ARRAY_BUFFER, 
                         node->meshData->vertices.size() * sizeof(glm::vec3),
                         node->meshData->vertices.data(), 
                         GL_STATIC_DRAW);
            
            // Position attribute
            glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, sizeof(glm::vec3), (void*)0);
            glEnableVertexAttribArray(0);
            
            // Upload indices
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, gpuMesh.ebo);
            glBufferData(GL_ELEMENT_ARRAY_BUFFER,
                         node->meshData->indices.size() * sizeof(unsigned int),
                         node->meshData->indices.data(),
                         GL_STATIC_DRAW);
            
            glBindVertexArray(0);
            
            sceneMeshes.push_back(gpuMesh);
        }
        
        // Process children
        for (auto& child : node->children)
        {
            processMeshes(child.get());
        }
    };
    
    processMeshes(scene->root.get());
}

void SceneRenderer::clearScene()
{
    for (auto& mesh : sceneMeshes)
    {
        if (mesh.vao) glDeleteVertexArrays(1, &mesh.vao);
        if (mesh.vbo) glDeleteBuffers(1, &mesh.vbo);
        if (mesh.ebo) glDeleteBuffers(1, &mesh.ebo);
    }
    sceneMeshes.clear();
    currentScene = nullptr;
    hoveredNode = nullptr;
}

void SceneRenderer::render()
{
    if (fbo == 0) return;
    
    // Bind framebuffer
    glBindFramebuffer(GL_FRAMEBUFFER, fbo);
    glViewport(0, 0, viewportWidth, viewportHeight);
    
    // Clear with dark background
    glClearColor(0.15f, 0.15f, 0.18f, 1.0f);
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
    
    // Enable depth testing
    glEnable(GL_DEPTH_TEST);
    glDepthFunc(GL_LESS);
    
    // Enable line smoothing
    glEnable(GL_LINE_SMOOTH);
    glHint(GL_LINE_SMOOTH_HINT, GL_NICEST);
    
    // Calculate view-projection matrix
    float aspectRatio = static_cast<float>(viewportWidth) / static_cast<float>(viewportHeight);
    glm::mat4 view = camera.getViewMatrix();
    glm::mat4 projection = camera.getProjectionMatrix(aspectRatio);
    glm::mat4 viewProjection = projection * view;
    
    // Draw grid
    glUseProgram(lineShaderProgram);
    GLint vpLoc = glGetUniformLocation(lineShaderProgram, "uViewProjection");
    glUniformMatrix4fv(vpLoc, 1, GL_FALSE, &viewProjection[0][0]);
    
    glBindVertexArray(gridVAO);
    glLineWidth(1.0f);
    glDrawArrays(GL_LINES, 0, gridVertexCount);
    
    // Draw scene meshes
    if (!sceneMeshes.empty())
    {
        glUseProgram(meshShaderProgram);
        GLint meshVpLoc = glGetUniformLocation(meshShaderProgram, "uViewProjection");
        GLint colorLoc = glGetUniformLocation(meshShaderProgram, "uColor");
        glUniformMatrix4fv(meshVpLoc, 1, GL_FALSE, &viewProjection[0][0]);
        
        for (const auto& mesh : sceneMeshes)
        {
            glUniform3fv(colorLoc, 1, &mesh.color[0]);
            glBindVertexArray(mesh.vao);
            glDrawElements(GL_TRIANGLES, mesh.indexCount, GL_UNSIGNED_INT, 0);
        }
        
        // Draw outline for hovered mesh
        for (const auto& mesh : sceneMeshes)
        {
            if (mesh.sceneNode == hoveredNode && hoveredNode != nullptr)
            {
                renderOutline(mesh, viewProjection);
            }
        }
    }
    
    // Draw axes (on top)
    glUseProgram(lineShaderProgram);
    glBindVertexArray(axesVAO);
    glLineWidth(3.0f);
    glDrawArrays(GL_LINES, 0, axesVertexCount);
    
    // Draw axis cone arrowheads
    glBindVertexArray(axesConeVAO);
    glDrawArrays(GL_TRIANGLES, 0, axesConeVertexCount);
    
    // Cleanup state
    glBindVertexArray(0);
    glUseProgram(0);
    glBindFramebuffer(GL_FRAMEBUFFER, 0);
}

void SceneRenderer::renderOutline(const GPUMesh& mesh, const glm::mat4& viewProjection)
{
    if (!mesh.sceneNode || !mesh.sceneNode->meshData || mesh.sceneNode->meshData->vertices.empty())
    {
        return;
    }
    
    // Calculate bounding box from mesh vertices
    const auto& vertices = mesh.sceneNode->meshData->vertices;
    glm::vec3 minBounds = vertices[0];
    glm::vec3 maxBounds = vertices[0];
    
    for (const auto& v : vertices)
    {
        minBounds = glm::min(minBounds, v);
        maxBounds = glm::max(maxBounds, v);
    }
    
    // Add small padding to avoid z-fighting
    glm::vec3 padding(0.01f);
    minBounds -= padding;
    maxBounds += padding;
    
    // Create bounding box line vertices (12 edges = 24 vertices)
    float boxVertices[] = {
        // Bottom face edges
        minBounds.x, minBounds.y, minBounds.z,  maxBounds.x, minBounds.y, minBounds.z,
        maxBounds.x, minBounds.y, minBounds.z,  maxBounds.x, minBounds.y, maxBounds.z,
        maxBounds.x, minBounds.y, maxBounds.z,  minBounds.x, minBounds.y, maxBounds.z,
        minBounds.x, minBounds.y, maxBounds.z,  minBounds.x, minBounds.y, minBounds.z,
        // Top face edges
        minBounds.x, maxBounds.y, minBounds.z,  maxBounds.x, maxBounds.y, minBounds.z,
        maxBounds.x, maxBounds.y, minBounds.z,  maxBounds.x, maxBounds.y, maxBounds.z,
        maxBounds.x, maxBounds.y, maxBounds.z,  minBounds.x, maxBounds.y, maxBounds.z,
        minBounds.x, maxBounds.y, maxBounds.z,  minBounds.x, maxBounds.y, minBounds.z,
        // Vertical edges
        minBounds.x, minBounds.y, minBounds.z,  minBounds.x, maxBounds.y, minBounds.z,
        maxBounds.x, minBounds.y, minBounds.z,  maxBounds.x, maxBounds.y, minBounds.z,
        maxBounds.x, minBounds.y, maxBounds.z,  maxBounds.x, maxBounds.y, maxBounds.z,
        minBounds.x, minBounds.y, maxBounds.z,  minBounds.x, maxBounds.y, maxBounds.z,
    };
    
    // Create temporary VAO/VBO for bounding box
    GLuint boxVAO, boxVBO;
    glGenVertexArrays(1, &boxVAO);
    glGenBuffers(1, &boxVBO);
    
    glBindVertexArray(boxVAO);
    glBindBuffer(GL_ARRAY_BUFFER, boxVBO);
    glBufferData(GL_ARRAY_BUFFER, sizeof(boxVertices), boxVertices, GL_DYNAMIC_DRAW);
    
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 3 * sizeof(float), (void*)0);
    glEnableVertexAttribArray(0);
    
    // Setup shader
    glUseProgram(outlineShaderProgram);
    GLint vpLoc = glGetUniformLocation(outlineShaderProgram, "uViewProjection");
    GLint colorLoc = glGetUniformLocation(outlineShaderProgram, "uColor");
    
    glUniformMatrix4fv(vpLoc, 1, GL_FALSE, &viewProjection[0][0]);
    
    // Bright yellow outline color
    glm::vec3 outlineColor(1.0f, 0.9f, 0.3f);
    glUniform3fv(colorLoc, 1, &outlineColor[0]);
    
    // Draw bounding box lines
    glLineWidth(2.0f);
    glDisable(GL_DEPTH_TEST);
    
    glDrawArrays(GL_LINES, 0, 24);
    
    // Cleanup
    glEnable(GL_DEPTH_TEST);
    glBindVertexArray(0);
    glDeleteBuffers(1, &boxVBO);
    glDeleteVertexArrays(1, &boxVAO);
}

void SceneRenderer::cleanup()
{
    clearScene();
    
    if (gridVAO) { glDeleteVertexArrays(1, &gridVAO); gridVAO = 0; }
    if (gridVBO) { glDeleteBuffers(1, &gridVBO); gridVBO = 0; }
    if (axesVAO) { glDeleteVertexArrays(1, &axesVAO); axesVAO = 0; }
    if (axesVBO) { glDeleteBuffers(1, &axesVBO); axesVBO = 0; }
    if (axesConeVAO) { glDeleteVertexArrays(1, &axesConeVAO); axesConeVAO = 0; }
    if (axesConeVBO) { glDeleteBuffers(1, &axesConeVBO); axesConeVBO = 0; }
    if (lineShaderProgram) { glDeleteProgram(lineShaderProgram); lineShaderProgram = 0; }
    if (meshShaderProgram) { glDeleteProgram(meshShaderProgram); meshShaderProgram = 0; }
    if (outlineShaderProgram) { glDeleteProgram(outlineShaderProgram); outlineShaderProgram = 0; }
    if (fbo) { glDeleteFramebuffers(1, &fbo); fbo = 0; }
    if (colorTexture) { glDeleteTextures(1, &colorTexture); colorTexture = 0; }
    if (depthRenderbuffer) { glDeleteRenderbuffers(1, &depthRenderbuffer); depthRenderbuffer = 0; }
}

// ═══════════════════════════════════════════════════════════════════════════
// Object Picking
// ═══════════════════════════════════════════════════════════════════════════

SceneNode* SceneRenderer::pickObject(float mouseX, float mouseY)
{
    if (!currentScene || !currentScene->root || viewportWidth == 0 || viewportHeight == 0)
    {
        return nullptr;
    }
    
    // Convert mouse coordinates to normalized device coordinates
    // mouseX, mouseY are in viewport coordinates (0,0 = top-left)
    float ndcX = (2.0f * mouseX) / viewportWidth - 1.0f;
    float ndcY = 1.0f - (2.0f * mouseY) / viewportHeight;  // Flip Y
    
    // Get camera matrices
    float aspectRatio = static_cast<float>(viewportWidth) / static_cast<float>(viewportHeight);
    glm::mat4 view = camera.getViewMatrix();
    glm::mat4 projection = camera.getProjectionMatrix(aspectRatio);
    
    // Inverse matrices for unprojecting
    glm::mat4 invProjection = glm::inverse(projection);
    glm::mat4 invView = glm::inverse(view);
    
    // Create ray in view space
    glm::vec4 rayClipNear(ndcX, ndcY, -1.0f, 1.0f);
    glm::vec4 rayClipFar(ndcX, ndcY, 1.0f, 1.0f);
    
    glm::vec4 rayViewNear = invProjection * rayClipNear;
    glm::vec4 rayViewFar = invProjection * rayClipFar;
    rayViewNear /= rayViewNear.w;
    rayViewFar /= rayViewFar.w;
    
    // Transform to world space
    glm::vec4 rayWorldNear = invView * rayViewNear;
    glm::vec4 rayWorldFar = invView * rayViewFar;
    
    glm::vec3 rayOrigin = glm::vec3(rayWorldNear);
    glm::vec3 rayDir = glm::normalize(glm::vec3(rayWorldFar - rayWorldNear));
    
    // Test intersection with all meshes
    SceneNode* closestNode = nullptr;
    float closestDistance = std::numeric_limits<float>::max();
    
    for (const auto& mesh : sceneMeshes)
    {
        if (mesh.sceneNode)
        {
            float distance;
            if (rayIntersectsMesh(rayOrigin, rayDir, mesh.sceneNode, distance))
            {
                if (distance < closestDistance)
                {
                    closestDistance = distance;
                    closestNode = mesh.sceneNode;
                }
            }
        }
    }
    
    return closestNode;
}

bool SceneRenderer::rayIntersectsMesh(const glm::vec3& rayOrigin, const glm::vec3& rayDir, 
                                       SceneNode* node, float& outDistance)
{
    if (!node || !node->meshData || node->meshData->vertices.empty())
    {
        return false;
    }
    
    const auto& vertices = node->meshData->vertices;
    const auto& indices = node->meshData->indices;
    
    bool hit = false;
    outDistance = std::numeric_limits<float>::max();
    
    // Test each triangle
    for (size_t i = 0; i + 2 < indices.size(); i += 3)
    {
        const glm::vec3& v0 = vertices[indices[i]];
        const glm::vec3& v1 = vertices[indices[i + 1]];
        const glm::vec3& v2 = vertices[indices[i + 2]];
        
        float t;
        if (rayIntersectsTriangle(rayOrigin, rayDir, v0, v1, v2, t))
        {
            if (t > 0 && t < outDistance)
            {
                outDistance = t;
                hit = true;
            }
        }
    }
    
    return hit;
}

// Möller–Trumbore ray-triangle intersection algorithm
bool SceneRenderer::rayIntersectsTriangle(const glm::vec3& rayOrigin, const glm::vec3& rayDir,
                                           const glm::vec3& v0, const glm::vec3& v1, const glm::vec3& v2,
                                           float& outT)
{
    const float EPSILON = 0.0000001f;
    
    glm::vec3 edge1 = v1 - v0;
    glm::vec3 edge2 = v2 - v0;
    glm::vec3 h = glm::cross(rayDir, edge2);
    float a = glm::dot(edge1, h);
    
    if (a > -EPSILON && a < EPSILON)
    {
        return false;  // Ray is parallel to triangle
    }
    
    float f = 1.0f / a;
    glm::vec3 s = rayOrigin - v0;
    float u = f * glm::dot(s, h);
    
    if (u < 0.0f || u > 1.0f)
    {
        return false;
    }
    
    glm::vec3 q = glm::cross(s, edge1);
    float v = f * glm::dot(rayDir, q);
    
    if (v < 0.0f || u + v > 1.0f)
    {
        return false;
    }
    
    float t = f * glm::dot(edge2, q);
    
    if (t > EPSILON)
    {
        outT = t;
        return true;
    }
    
    return false;
}

// ═══════════════════════════════════════════════════════════════════════════
// Private Initialization Methods
// ═══════════════════════════════════════════════════════════════════════════

void SceneRenderer::createFramebuffer(int width, int height)
{
    viewportWidth = width;
    viewportHeight = height;
    
    // Create color texture
    glGenTextures(1, &colorTexture);
    glBindTexture(GL_TEXTURE_2D, colorTexture);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, width, height, 0, GL_RGB, GL_UNSIGNED_BYTE, nullptr);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glBindTexture(GL_TEXTURE_2D, 0);
    
    // Create depth renderbuffer
    glGenRenderbuffers(1, &depthRenderbuffer);
    glBindRenderbuffer(GL_RENDERBUFFER, depthRenderbuffer);
    glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT24, width, height);
    glBindRenderbuffer(GL_RENDERBUFFER, 0);
    
    // Create framebuffer
    glGenFramebuffers(1, &fbo);
    glBindFramebuffer(GL_FRAMEBUFFER, fbo);
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, colorTexture, 0);
    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, depthRenderbuffer);
    
    // Check framebuffer completeness
    if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE)
    {
        fprintf(stderr, "ERROR: Framebuffer is not complete!\n");
    }
    
    glBindFramebuffer(GL_FRAMEBUFFER, 0);
}

void SceneRenderer::createShaders()
{
    // Line shader (for grid and axes)
    GLuint lineVS = compileShader(LINE_VERTEX_SHADER, GL_VERTEX_SHADER);
    GLuint lineFS = compileShader(LINE_FRAGMENT_SHADER, GL_FRAGMENT_SHADER);
    lineShaderProgram = linkProgram(lineVS, lineFS);
    glDeleteShader(lineVS);
    glDeleteShader(lineFS);
    
    // Mesh shader (for scene meshes)
    GLuint meshVS = compileShader(MESH_VERTEX_SHADER, GL_VERTEX_SHADER);
    GLuint meshFS = compileShader(MESH_FRAGMENT_SHADER, GL_FRAGMENT_SHADER);
    meshShaderProgram = linkProgram(meshVS, meshFS);
    glDeleteShader(meshVS);
    glDeleteShader(meshFS);
    
    // Outline shader (for hover highlight)
    GLuint outlineVS = compileShader(OUTLINE_VERTEX_SHADER, GL_VERTEX_SHADER);
    GLuint outlineFS = compileShader(OUTLINE_FRAGMENT_SHADER, GL_FRAGMENT_SHADER);
    outlineShaderProgram = linkProgram(outlineVS, outlineFS);
    glDeleteShader(outlineVS);
    glDeleteShader(outlineFS);
}

void SceneRenderer::createGridMesh()
{
    // Create grid lines on XZ plane - large expansive grid
    const float gridExtent = 500.0f;   // Grid extends -500 to +500 units
    const float majorSpacing = 10.0f;  // Major grid lines every 10 units
    const float minorSpacing = 1.0f;   // Minor grid lines every 1 unit (only near center)
    const float minorExtent = 50.0f;   // Minor lines only within ±50 units of center
    
    const glm::vec3 majorColor(0.25f, 0.25f, 0.3f);
    const glm::vec3 minorColor(0.2f, 0.2f, 0.22f);
    const glm::vec3 centerLineColor(0.4f, 0.4f, 0.45f);
    
    std::vector<float> vertices;
    
    auto addLine = [&](float x1, float z1, float x2, float z2, const glm::vec3& color) {
        vertices.push_back(x1); vertices.push_back(0.0f); vertices.push_back(z1);
        vertices.push_back(color.r); vertices.push_back(color.g); vertices.push_back(color.b);
        vertices.push_back(x2); vertices.push_back(0.0f); vertices.push_back(z2);
        vertices.push_back(color.r); vertices.push_back(color.g); vertices.push_back(color.b);
    };
    
    // Major grid lines (every 10 units across entire grid)
    for (float i = -gridExtent; i <= gridExtent; i += majorSpacing)
    {
        glm::vec3 color = (i == 0.0f) ? centerLineColor : majorColor;
        addLine(-gridExtent, i, gridExtent, i, color);  // Lines along X
        addLine(i, -gridExtent, i, gridExtent, color);  // Lines along Z
    }
    
    // Minor grid lines (every 1 unit, only near center for detail)
    for (float i = -minorExtent; i <= minorExtent; i += minorSpacing)
    {
        // Skip if this would overlap with a major line
        if (fmod(std::abs(i), majorSpacing) < 0.001f) continue;
        
        addLine(-minorExtent, i, minorExtent, i, minorColor);  // Lines along X
        addLine(i, -minorExtent, i, minorExtent, minorColor);  // Lines along Z
    }
    
    gridVertexCount = static_cast<int>(vertices.size() / 6);
    
    // Create VAO/VBO
    glGenVertexArrays(1, &gridVAO);
    glGenBuffers(1, &gridVBO);
    
    glBindVertexArray(gridVAO);
    glBindBuffer(GL_ARRAY_BUFFER, gridVBO);
    glBufferData(GL_ARRAY_BUFFER, vertices.size() * sizeof(float), vertices.data(), GL_STATIC_DRAW);
    
    // Position attribute
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 6 * sizeof(float), (void*)0);
    glEnableVertexAttribArray(0);
    
    // Color attribute
    glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 6 * sizeof(float), (void*)(3 * sizeof(float)));
    glEnableVertexAttribArray(1);
    
    glBindVertexArray(0);
}

void SceneRenderer::createAxesMesh()
{
    // Axes: X=Red, Y=Green, Z=Blue (prominent colors)
    const float axisLength = 3.0f;
    const float coneLength = 0.3f;   // Length of cone arrowhead
    const float coneRadius = 0.08f;  // Radius of cone base
    const int coneSegments = 12;     // Number of segments for smooth cone
    
    // Axis line vertices (shorter to make room for cone)
    float lineVertices[] = {
        // X axis (bright red)
        0.0f, 0.0f, 0.0f,  1.0f, 0.2f, 0.2f,
        axisLength - coneLength, 0.0f, 0.0f,  1.0f, 0.2f, 0.2f,
        
        // Y axis (bright green)
        0.0f, 0.0f, 0.0f,  0.2f, 1.0f, 0.2f,
        0.0f, axisLength - coneLength, 0.0f,  0.2f, 1.0f, 0.2f,
        
        // Z axis (bright blue)
        0.0f, 0.0f, 0.0f,  0.3f, 0.6f, 1.0f,
        0.0f, 0.0f, axisLength - coneLength,  0.3f, 0.6f, 1.0f,
    };
    
    axesVertexCount = 6;  // 3 axes * 2 vertices each
    
    glGenVertexArrays(1, &axesVAO);
    glGenBuffers(1, &axesVBO);
    
    glBindVertexArray(axesVAO);
    glBindBuffer(GL_ARRAY_BUFFER, axesVBO);
    glBufferData(GL_ARRAY_BUFFER, sizeof(lineVertices), lineVertices, GL_STATIC_DRAW);
    
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 6 * sizeof(float), (void*)0);
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 6 * sizeof(float), (void*)(3 * sizeof(float)));
    glEnableVertexAttribArray(1);
    
    glBindVertexArray(0);
    
    // Create cone arrowheads (triangles)
    std::vector<float> coneVertices;
    
    // Helper to add a cone along an axis
    auto addCone = [&](glm::vec3 tip, glm::vec3 direction, glm::vec3 color) {
        // Calculate perpendicular vectors for the cone base
        glm::vec3 perp1, perp2;
        if (std::abs(direction.x) < 0.9f) {
            perp1 = glm::normalize(glm::cross(direction, glm::vec3(1, 0, 0)));
        } else {
            perp1 = glm::normalize(glm::cross(direction, glm::vec3(0, 1, 0)));
        }
        perp2 = glm::normalize(glm::cross(direction, perp1));
        
        glm::vec3 baseCenter = tip - direction * coneLength;
        
        // Generate cone triangles
        for (int i = 0; i < coneSegments; ++i) {
            float angle1 = (2.0f * 3.14159265f * i) / coneSegments;
            float angle2 = (2.0f * 3.14159265f * (i + 1)) / coneSegments;
            
            glm::vec3 p1 = baseCenter + coneRadius * (std::cos(angle1) * perp1 + std::sin(angle1) * perp2);
            glm::vec3 p2 = baseCenter + coneRadius * (std::cos(angle2) * perp1 + std::sin(angle2) * perp2);
            
            // Side triangle (tip, p1, p2)
            coneVertices.push_back(tip.x); coneVertices.push_back(tip.y); coneVertices.push_back(tip.z);
            coneVertices.push_back(color.r); coneVertices.push_back(color.g); coneVertices.push_back(color.b);
            coneVertices.push_back(p1.x); coneVertices.push_back(p1.y); coneVertices.push_back(p1.z);
            coneVertices.push_back(color.r); coneVertices.push_back(color.g); coneVertices.push_back(color.b);
            coneVertices.push_back(p2.x); coneVertices.push_back(p2.y); coneVertices.push_back(p2.z);
            coneVertices.push_back(color.r); coneVertices.push_back(color.g); coneVertices.push_back(color.b);
            
            // Base triangle (baseCenter, p2, p1) - reversed winding for correct facing
            coneVertices.push_back(baseCenter.x); coneVertices.push_back(baseCenter.y); coneVertices.push_back(baseCenter.z);
            coneVertices.push_back(color.r); coneVertices.push_back(color.g); coneVertices.push_back(color.b);
            coneVertices.push_back(p2.x); coneVertices.push_back(p2.y); coneVertices.push_back(p2.z);
            coneVertices.push_back(color.r); coneVertices.push_back(color.g); coneVertices.push_back(color.b);
            coneVertices.push_back(p1.x); coneVertices.push_back(p1.y); coneVertices.push_back(p1.z);
            coneVertices.push_back(color.r); coneVertices.push_back(color.g); coneVertices.push_back(color.b);
        }
    };
    
    // X cone (red)
    addCone(glm::vec3(axisLength, 0, 0), glm::vec3(1, 0, 0), glm::vec3(1.0f, 0.2f, 0.2f));
    // Y cone (green)
    addCone(glm::vec3(0, axisLength, 0), glm::vec3(0, 1, 0), glm::vec3(0.2f, 1.0f, 0.2f));
    // Z cone (blue)
    addCone(glm::vec3(0, 0, axisLength), glm::vec3(0, 0, 1), glm::vec3(0.3f, 0.6f, 1.0f));
    
    axesConeVertexCount = static_cast<int>(coneVertices.size() / 6);
    
    glGenVertexArrays(1, &axesConeVAO);
    glGenBuffers(1, &axesConeVBO);
    
    glBindVertexArray(axesConeVAO);
    glBindBuffer(GL_ARRAY_BUFFER, axesConeVBO);
    glBufferData(GL_ARRAY_BUFFER, coneVertices.size() * sizeof(float), coneVertices.data(), GL_STATIC_DRAW);
    
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 6 * sizeof(float), (void*)0);
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 6 * sizeof(float), (void*)(3 * sizeof(float)));
    glEnableVertexAttribArray(1);
    
    glBindVertexArray(0);
}

GLuint SceneRenderer::compileShader(const char* source, unsigned int type)
{
    GLuint shader = glCreateShader(type);
    glShaderSource(shader, 1, &source, nullptr);
    glCompileShader(shader);
    
    // Check for errors
    int success;
    glGetShaderiv(shader, GL_COMPILE_STATUS, &success);
    if (!success)
    {
        char infoLog[512];
        glGetShaderInfoLog(shader, 512, nullptr, infoLog);
        fprintf(stderr, "ERROR: Shader compilation failed:\n%s\n", infoLog);
    }
    
    return shader;
}

GLuint SceneRenderer::linkProgram(GLuint vertexShader, GLuint fragmentShader)
{
    GLuint program = glCreateProgram();
    glAttachShader(program, vertexShader);
    glAttachShader(program, fragmentShader);
    glLinkProgram(program);
    
    // Check for errors
    int success;
    glGetProgramiv(program, GL_LINK_STATUS, &success);
    if (!success)
    {
        char infoLog[512];
        glGetProgramInfoLog(program, 512, nullptr, infoLog);
        fprintf(stderr, "ERROR: Shader program linking failed:\n%s\n", infoLog);
    }
    
    return program;
}
