#include "scene.h"

#include <tinyusdz.hh>
#include <fstream>
#include <sstream>
#include <algorithm>
#include <iostream>

// ═══════════════════════════════════════════════════════════════════════════
// SceneNode Implementation
// ═══════════════════════════════════════════════════════════════════════════

SceneNode::SceneNode(const std::string& nodeName, PrimType nodeType)
    : name(nodeName), type(nodeType)
{
    if (type == PrimType::Mesh)
    {
        meshData = std::make_unique<MeshData>();
    }
}

SceneNode* SceneNode::addChild(const std::string& childName, PrimType childType)
{
    auto child = std::make_unique<SceneNode>(childName, childType);
    child->parent = this;
    children.push_back(std::move(child));
    return children.back().get();
}

SceneNode* SceneNode::findChild(const std::string& childName) const
{
    for (const auto& child : children)
    {
        if (child->name == childName)
        {
            return child.get();
        }
    }
    return nullptr;
}

bool SceneNode::removeChild(SceneNode* child)
{
    for (auto it = children.begin(); it != children.end(); ++it)
    {
        if (it->get() == child)
        {
            children.erase(it);
            return true;
        }
    }
    return false;
}

// ═══════════════════════════════════════════════════════════════════════════
// Scene Implementation
// ═══════════════════════════════════════════════════════════════════════════

Scene::Scene()
{
    root = std::make_unique<SceneNode>("World", PrimType::Xform);
}



// ═══════════════════════════════════════════════════════════════════════════
// USD Parsing
// ═══════════════════════════════════════════════════════════════════════════

bool Scene::loadFromFile(const std::filesystem::path& path)
{
    clear();
    
    if (!std::filesystem::exists(path))
    {
        return false;
    }
    
    tinyusdz::Stage stage;
    std::string warn, err;
    
    // LoadUSDFromFile handles .usda, .usdc, and .usdz automatically
    bool ret = tinyusdz::LoadUSDFromFile(path.string(), &stage, &warn, &err);
    
    if (!warn.empty()) {
        std::cout << "USD Load Warning: " << warn << std::endl;
    }
    
    if (!ret) {
        std::cerr << "USD Load Error: " << err << std::endl;
        return false;
    }
    
    name = path.stem().string();
    
    // Get metadata if available
    // upAxis = stage.metas().upAxis.value_or("Y"); ... (API might vary, using defaults for now)
    
    // Traverse all root prims and convert to Kiln SceneNodes
    for (const auto& prim : stage.root_prims())
    {
        processTinyUSDZPrim(prim, root.get());
    }
    
    return true;
}

bool Scene::saveToFile(const std::filesystem::path& path) const
{
    std::ofstream file(path);
    if (!file.is_open())
    {
        return false;
    }
    
    file << generateUSDA();
    file.close();
    return true;
}

void Scene::clear()
{
    name.clear();
    upAxis = "Y";
    metersPerUnit = 1.0f;
    defaultPrim = "World";
    root = std::make_unique<SceneNode>("World", PrimType::Xform);
}

SceneNode* Scene::findNodeByPath(const std::string& path) const
{
    if (!root || path.empty())
    {
        return nullptr;
    }
    
    // Split path by '/'
    std::vector<std::string> parts;
    std::stringstream ss(path);
    std::string part;
    while (std::getline(ss, part, '/'))
    {
        if (!part.empty())
        {
            parts.push_back(part);
        }
    }
    
    if (parts.empty())
    {
        return nullptr;
    }
    
    // First part should match root
    if (parts[0] != root->name)
    {
        return nullptr;
    }
    
    SceneNode* current = root.get();
    for (size_t i = 1; i < parts.size(); ++i)
    {
        current = current->findChild(parts[i]);
        if (!current)
        {
            return nullptr;
        }
    }
    
    return current;
}

// ═══════════════════════════════════════════════════════════════════════════
// TinyUSDZ Conversion
// ═══════════════════════════════════════════════════════════════════════════

void Scene::processTinyUSDZPrim(const tinyusdz::Prim& prim, SceneNode* parent)
{
    PrimType type = PrimType::Xform;
    std::string primType = prim.type_name();
    
    // Map USD type to Kiln PrimType
    if (primType == "Mesh") type = PrimType::Mesh;
    else if (primType == "Scope") type = PrimType::Scope;
    else if (primType == "Xform") type = PrimType::Xform;
    
    // Use the element name (leaf name) for the node
    SceneNode* node = parent->addChild(prim.element_name(), type);
    
    // Process Mesh data
    if (const tinyusdz::GeomMesh* mesh = prim.as<tinyusdz::GeomMesh>())
    {
        // Get pointers to data (TinyUSDZ returns copies for now via helper methods)
        // In v0.9.0 we use get_points().
        std::vector<tinyusdz::value::point3f> points = mesh->get_points();
        
        node->meshData->vertices.reserve(points.size());
        for (const auto& p : points)
        {
            node->meshData->vertices.emplace_back(p.x, p.y, p.z);
        }
        
        // Face counts and indices
        std::vector<int> counts = mesh->get_faceVertexCounts();
        std::vector<int> indices = mesh->get_faceVertexIndices();
        
        // Triangulate
        size_t vertexOffset = 0;
        node->meshData->indices.reserve(indices.size()); // Approximation
        
        for (int count : counts)
        {
            if (vertexOffset + count > indices.size()) break; // Safety check
            
            if (count == 3)
            {
                node->meshData->indices.push_back(static_cast<unsigned int>(indices[vertexOffset]));
                node->meshData->indices.push_back(static_cast<unsigned int>(indices[vertexOffset + 1]));
                node->meshData->indices.push_back(static_cast<unsigned int>(indices[vertexOffset + 2]));
            }
            else if (count == 4)
            {
                // Triangle 1
                node->meshData->indices.push_back(static_cast<unsigned int>(indices[vertexOffset]));
                node->meshData->indices.push_back(static_cast<unsigned int>(indices[vertexOffset + 1]));
                node->meshData->indices.push_back(static_cast<unsigned int>(indices[vertexOffset + 2]));
                // Triangle 2
                node->meshData->indices.push_back(static_cast<unsigned int>(indices[vertexOffset]));
                node->meshData->indices.push_back(static_cast<unsigned int>(indices[vertexOffset + 2]));
                node->meshData->indices.push_back(static_cast<unsigned int>(indices[vertexOffset + 3]));
            }
            else if (count > 4)
            {
                // Simple fan triangulation for N-gons
                for (int i = 1; i < count - 1; ++i)
                {
                    node->meshData->indices.push_back(static_cast<unsigned int>(indices[vertexOffset]));
                    node->meshData->indices.push_back(static_cast<unsigned int>(indices[vertexOffset + i]));
                    node->meshData->indices.push_back(static_cast<unsigned int>(indices[vertexOffset + i + 1]));
                }
            }
            vertexOffset += count;
        }
        
        // Display Color
        tinyusdz::value::color3f color;
        if (mesh->get_displayColor(&color)) 
        {
            node->meshData->displayColor = glm::vec3(color.r, color.g, color.b);
        }
    }
    
    // Recurse to children
    for (const auto& child : prim.children())
    {
        processTinyUSDZPrim(child, node);
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// USD Generation
// ═══════════════════════════════════════════════════════════════════════════

std::string Scene::generateUSDA() const
{
    std::string output = "#usda 1.0\n";
    output += "(\n";
    output += "    defaultPrim = \"" + defaultPrim + "\"\n";
    output += "    metersPerUnit = " + std::to_string(static_cast<int>(metersPerUnit)) + "\n";
    output += "    upAxis = \"" + upAxis + "\"\n";
    output += ")\n\n";
    
    if (root)
    {
        generateNodeUSDA(root.get(), output, 0);
    }
    
    return output;
}

void Scene::generateNodeUSDA(const SceneNode* node, std::string& output, int indent) const
{
    std::string indentStr(indent * 4, ' ');
    
    // Check if this mesh has PhysicsCollisionAPI
    bool hasCollision = (node->type == PrimType::Mesh && node->meshData && node->meshData->collision);
    
    output += indentStr + "def " + primTypeToString(node->type) + " \"" + node->name + "\"";
    
    if (hasCollision)
    {
        output += " (\n";
        output += indentStr + "    prepend apiSchemas = [\"PhysicsCollisionAPI\"]\n";
        output += indentStr + ")";
    }
    output += "\n";
    output += indentStr + "{\n";
    
    if (node->type == PrimType::Mesh && node->meshData && !node->meshData->vertices.empty())
    {
        const MeshData& mesh = *node->meshData;
        std::string innerIndent = indentStr + "    ";
        
        // Compute extent
        glm::vec3 minExt(FLT_MAX), maxExt(-FLT_MAX);
        for (const auto& v : mesh.vertices)
        {
            minExt = glm::min(minExt, v);
            maxExt = glm::max(maxExt, v);
        }
        
        output += innerIndent + "float3[] extent = [(" + 
                  std::to_string(minExt.x) + ", " + std::to_string(minExt.y) + ", " + std::to_string(minExt.z) + "), (" +
                  std::to_string(maxExt.x) + ", " + std::to_string(maxExt.y) + ", " + std::to_string(maxExt.z) + ")]\n";
        
        size_t faceCount = mesh.indices.size() / 3;
        output += innerIndent + "int[] faceVertexCounts = [";
        for (size_t i = 0; i < faceCount; ++i)
        {
            output += "3";
            if (i < faceCount - 1) output += ", ";
        }
        output += "]\n";
        
        output += innerIndent + "int[] faceVertexIndices = [";
        for (size_t i = 0; i < mesh.indices.size(); ++i)
        {
            output += std::to_string(mesh.indices[i]);
            if (i < mesh.indices.size() - 1) output += ", ";
        }
        output += "]\n";
        
        output += innerIndent + "point3f[] points = [";
        for (size_t i = 0; i < mesh.vertices.size(); ++i)
        {
            const auto& v = mesh.vertices[i];
            output += "(" + std::to_string(v.x) + ", " + std::to_string(v.y) + ", " + std::to_string(v.z) + ")";
            if (i < mesh.vertices.size() - 1) output += ", ";
        }
        output += "]\n";
        
        output += innerIndent + "color3f[] primvars:displayColor = [(" +
                  std::to_string(mesh.displayColor.r) + ", " +
                  std::to_string(mesh.displayColor.g) + ", " +
                  std::to_string(mesh.displayColor.b) + ")]\n";
        
        // Write physics collision property if collision is enabled
        if (mesh.collision)
        {
            output += innerIndent + "bool physics:collisionEnabled = true\n";
        }
    }
    
    for (const auto& child : node->children)
    {
        generateNodeUSDA(child.get(), output, indent + 1);
    }
    
    output += indentStr + "}\n";
}
