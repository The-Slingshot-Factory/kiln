#pragma once

#include "camera.h"
#include "../scene/scene.h"

#include <glm/glm.hpp>
#include <glm/gtc/matrix_transform.hpp>
#include <vector>

// Forward declare to avoid including GL headers in header
typedef unsigned int GLuint;
typedef int GLint;

// GPU representation of a mesh with reference to scene node
struct GPUMesh
{
    GLuint vao = 0;
    GLuint vbo = 0;
    GLuint ebo = 0;
    int indexCount = 0;
    glm::vec3 color = glm::vec3(0.5f);
    SceneNode* sceneNode = nullptr;  // Reference back to scene node for picking
};

class SceneRenderer
{
public:
    SceneRenderer();
    ~SceneRenderer();

    // Initialize OpenGL resources (call after OpenGL context is ready)
    void init(int width, int height);
    
    // Resize the framebuffer (call when viewport size changes)
    void resize(int width, int height);
    
    // Load scene meshes into GPU buffers
    void setScene(const Scene* scene);
    
    // Clear loaded scene meshes
    void clearScene();
    
    // Render the scene to the framebuffer
    void render();
    
    // Cleanup OpenGL resources
    void cleanup();
    
    // Get the rendered texture ID for ImGui::Image()
    GLuint getTextureID() const { return colorTexture; }
    
    // Camera access for input handling
    Camera& getCamera() { return camera; }
    const Camera& getCamera() const { return camera; }
    
    // Object picking - returns SceneNode under mouse position (nullptr if none)
    // mouseX, mouseY are in viewport coordinates (0,0 = top-left)
    SceneNode* pickObject(float mouseX, float mouseY);
    
    // Hover/selection state for highlighting
    void setHoveredNode(SceneNode* node) { hoveredNode = node; }
    SceneNode* getHoveredNode() const { return hoveredNode; }

private:
    // Framebuffer
    GLuint fbo = 0;
    GLuint colorTexture = 0;
    GLuint depthRenderbuffer = 0;
    int viewportWidth = 0;
    int viewportHeight = 0;
    
    // Shaders
    GLuint lineShaderProgram = 0;    // For grid and axes
    GLuint meshShaderProgram = 0;    // For scene meshes
    GLuint outlineShaderProgram = 0; // For hover outline
    
    // Grid mesh
    GLuint gridVAO = 0;
    GLuint gridVBO = 0;
    int gridVertexCount = 0;
    
    // Axes mesh (lines)
    GLuint axesVAO = 0;
    GLuint axesVBO = 0;
    int axesVertexCount = 0;
    
    // Axes cone arrowheads (triangles)
    GLuint axesConeVAO = 0;
    GLuint axesConeVBO = 0;
    int axesConeVertexCount = 0;
    
    // Scene meshes (loaded from Scene)
    std::vector<GPUMesh> sceneMeshes;
    
    // Hover state
    SceneNode* hoveredNode = nullptr;
    
    // Scene reference for picking
    const Scene* currentScene = nullptr;
    
    // Camera
    Camera camera;
    
    // Initialization helpers
    void createFramebuffer(int width, int height);
    void createShaders();
    void createGridMesh();
    void createAxesMesh();
    
    // Rendering helpers
    void renderOutline(const GPUMesh& mesh, const glm::mat4& viewProjection);
    
    // Picking helpers
    bool rayIntersectsMesh(const glm::vec3& rayOrigin, const glm::vec3& rayDir, 
                           SceneNode* node, float& outDistance);
    bool rayIntersectsTriangle(const glm::vec3& rayOrigin, const glm::vec3& rayDir,
                               const glm::vec3& v0, const glm::vec3& v1, const glm::vec3& v2,
                               float& outT);
    
    // Shader compilation
    GLuint compileShader(const char* source, unsigned int type);
    GLuint linkProgram(GLuint vertexShader, GLuint fragmentShader);
};
