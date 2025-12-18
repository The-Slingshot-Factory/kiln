#pragma once

#include <glm/glm.hpp>
#include <string>
#include <vector>
#include <memory>
#include <filesystem>

// ═══════════════════════════════════════════════════════════════════════════
// OpenUSD Prim Types
// ═══════════════════════════════════════════════════════════════════════════

namespace tinyusdz { class Prim; }

enum class PrimType
{
    Xform,      // Transform node - can contain children
    Mesh,       // Geometry primitive with vertices/faces
    Scope       // Logical grouping without transform
};

// Convert prim type to string (for USD file generation)
inline const char* primTypeToString(PrimType type)
{
    switch (type)
    {
        case PrimType::Xform: return "Xform";
        case PrimType::Mesh:  return "Mesh";
        case PrimType::Scope: return "Scope";
        default:              return "Xform";
    }
}

// Parse prim type from string
inline PrimType stringToPrimType(const std::string& str)
{
    if (str == "Xform") return PrimType::Xform;
    if (str == "Mesh")  return PrimType::Mesh;
    if (str == "Scope") return PrimType::Scope;
    return PrimType::Xform;  // Default to Xform for unknown types
}

// ═══════════════════════════════════════════════════════════════════════════
// Mesh Data (for Mesh prims)
// ═══════════════════════════════════════════════════════════════════════════

struct MeshData
{
    std::vector<glm::vec3> vertices;
    std::vector<unsigned int> indices;
    glm::vec3 displayColor = glm::vec3(0.5f);  // Default gray
    
    // Physics collision (UsdPhysicsCollisionAPI)
    bool collision = false;  // When true, applies PhysicsCollisionAPI with collisionEnabled=true
};

// ═══════════════════════════════════════════════════════════════════════════
// Scene Node - Base unit of the scene hierarchy (USD Prim)
// ═══════════════════════════════════════════════════════════════════════════

class SceneNode
{
public:
    SceneNode(const std::string& name, PrimType type = PrimType::Xform);
    ~SceneNode() = default;
    
    // Node identity
    std::string name;
    PrimType type = PrimType::Xform;
    
    // Mesh data (only valid if type == PrimType::Mesh)
    std::unique_ptr<MeshData> meshData;
    
    // Hierarchy
    SceneNode* parent = nullptr;
    std::vector<std::unique_ptr<SceneNode>> children;
    
    // Hierarchy operations
    SceneNode* addChild(const std::string& name, PrimType type = PrimType::Xform);
    SceneNode* findChild(const std::string& name) const;
    bool removeChild(SceneNode* child);
};

// ═══════════════════════════════════════════════════════════════════════════
// Scene - The root container (USD Stage)
// ═══════════════════════════════════════════════════════════════════════════

class Scene
{
public:
    Scene();
    
    // Load scene from USD file
    bool loadFromFile(const std::filesystem::path& filepath);
    
    // Save scene to USD file
    bool saveToFile(const std::filesystem::path& filepath) const;
    
    // Clear all scene data
    void clear();
    
    // Scene metadata (USD stage metadata)
    std::string name;
    std::string upAxis = "Y";
    float metersPerUnit = 1.0f;
    std::string defaultPrim = "World";
    
    // Scene hierarchy - root node (typically "World" Xform)
    std::unique_ptr<SceneNode> root;
    
    // Find node by path (e.g., "/World/GroundPlane")
    SceneNode* findNodeByPath(const std::string& path) const;
    
private:
    // USD parsing helpers (TinyUSDZ)
    void processTinyUSDZPrim(const tinyusdz::Prim& prim, SceneNode* parent);
    
    // USD generation helpers
    std::string generateUSDA() const;
    void generateNodeUSDA(const SceneNode* node, std::string& output, int indent) const;
};
