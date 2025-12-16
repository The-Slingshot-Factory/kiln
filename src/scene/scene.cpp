#include "scene.h"

#include <fstream>
#include <sstream>
#include <regex>
#include <algorithm>

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

bool Scene::loadFromFile(const std::filesystem::path& path)
{
    clear();
    
    if (!std::filesystem::exists(path))
    {
        return false;
    }
    
    std::ifstream file(path);
    if (!file.is_open())
    {
        return false;
    }
    
    std::stringstream buffer;
    buffer << file.rdbuf();
    std::string content = buffer.str();
    file.close();
    
    name = path.stem().string();
    
    std::string ext = path.extension().string();
    std::transform(ext.begin(), ext.end(), ext.begin(), ::tolower);
    
    if (ext == ".usda")
    {
        return parseUSDA(content);
    }
    
    return false;
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
// USD Parsing
// ═══════════════════════════════════════════════════════════════════════════

bool Scene::parseUSDA(const std::string& content)
{
    // Parse header metadata
    std::regex upAxisRegex(R"(upAxis\s*=\s*\"(\w+)\")");
    std::regex metersRegex(R"(metersPerUnit\s*=\s*([\d.]+))");
    std::regex defaultPrimRegex(R"(defaultPrim\s*=\s*\"(\w+)\")");
    
    std::smatch match;
    if (std::regex_search(content, match, upAxisRegex))
    {
        upAxis = match[1].str();
    }
    if (std::regex_search(content, match, metersRegex))
    {
        metersPerUnit = std::stof(match[1].str());
    }
    if (std::regex_search(content, match, defaultPrimRegex))
    {
        defaultPrim = match[1].str();
    }
    
    // Find root-level def blocks and parse recursively
    // Regex to capture def with optional metadata section: def Type "Name" (metadata) { or def Type "Name" {
    std::regex defRegex(R"(def\s+(\w+)\s+\"(\w+)\"\s*(?:\([^)]*\))?\s*\{)");
    
    std::string::const_iterator searchStart(content.cbegin());
    while (std::regex_search(searchStart, content.cend(), match, defRegex))
    {
        std::string primType = match[1].str();
        std::string primName = match[2].str();
        
        // Get the full match to check for apiSchemas in metadata
        std::string fullMatch = match[0].str();
        bool hasPhysicsCollisionAPI = (fullMatch.find("PhysicsCollisionAPI") != std::string::npos);
        
        size_t startPos = match.position() + (searchStart - content.cbegin());
        size_t bracePos = content.find('{', startPos);
        
        if (bracePos != std::string::npos)
        {
            int braceCount = 1;
            size_t endPos = bracePos + 1;
            
            while (braceCount > 0 && endPos < content.size())
            {
                if (content[endPos] == '{') braceCount++;
                else if (content[endPos] == '}') braceCount--;
                endPos++;
            }
            
            std::string blockContent = content.substr(bracePos + 1, endPos - bracePos - 2);
            
            if (primType == "Xform" && primName == defaultPrim)
            {
                root->name = primName;
                parseNode(blockContent, root.get(), 1);
            }
            else
            {
                PrimType type = stringToPrimType(primType);
                SceneNode* node = root->addChild(primName, type);
                
                if (type == PrimType::Mesh)
                {
                    parseMeshData(blockContent, *node->meshData);
                    // Also check metadata for PhysicsCollisionAPI
                    if (hasPhysicsCollisionAPI)
                    {
                        node->meshData->collision = true;
                    }
                }
                
                parseNode(blockContent, node, 1);
            }
            
            // Skip past the entire block we just parsed
            searchStart = content.cbegin() + endPos;
        }
        else
        {
            searchStart = match.suffix().first;
        }
    }
    
    return true;
}

void Scene::parseNode(const std::string& content, SceneNode* parent, int depth)
{
    if (depth > 10) return;  // Prevent infinite recursion
    
    // Regex to capture def with optional metadata section: def Type "Name" (metadata) { or def Type "Name" {
    std::regex defRegex(R"(def\s+(\w+)\s+\"(\w+)\"\s*(?:\([^)]*\))?\s*\{)");
    
    std::string::const_iterator searchStart(content.cbegin());
    std::smatch match;
    
    while (std::regex_search(searchStart, content.cend(), match, defRegex))
    {
        std::string primType = match[1].str();
        std::string primName = match[2].str();
        
        // Get the full match to check for apiSchemas in metadata
        std::string fullMatch = match[0].str();
        bool hasPhysicsCollisionAPI = (fullMatch.find("PhysicsCollisionAPI") != std::string::npos);
        
        size_t matchStart = match.position() + (searchStart - content.cbegin());
        size_t bracePos = content.find('{', matchStart);
        
        if (bracePos != std::string::npos)
        {
            int braceCount = 1;
            size_t endPos = bracePos + 1;
            
            while (braceCount > 0 && endPos < content.size())
            {
                if (content[endPos] == '{') braceCount++;
                else if (content[endPos] == '}') braceCount--;
                endPos++;
            }
            
            std::string blockContent = content.substr(bracePos + 1, endPos - bracePos - 2);
            
            PrimType type = stringToPrimType(primType);
            SceneNode* child = parent->addChild(primName, type);
            
            if (type == PrimType::Mesh)
            {
                parseMeshData(blockContent, *child->meshData);
                // Also check metadata for PhysicsCollisionAPI
                if (hasPhysicsCollisionAPI)
                {
                    child->meshData->collision = true;
                }
            }
            
            parseNode(blockContent, child, depth + 1);
            
            searchStart = content.cbegin() + endPos;
        }
        else
        {
            searchStart = match.suffix().first;
        }
    }
}

bool Scene::parseMeshData(const std::string& content, MeshData& meshData)
{
    // Parse points (vertices)
    std::regex pointsRegex(R"(point3f\[\]\s+points\s*=\s*\[([^\]]+)\])");
    std::smatch match;
    
    if (std::regex_search(content, match, pointsRegex))
    {
        std::string pointsStr = match[1].str();
        
        std::regex pointRegex(R"(\(\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\))");
        std::string::const_iterator searchStart(pointsStr.cbegin());
        
        while (std::regex_search(searchStart, pointsStr.cend(), match, pointRegex))
        {
            float x = std::stof(match[1].str());
            float y = std::stof(match[2].str());
            float z = std::stof(match[3].str());
            meshData.vertices.push_back(glm::vec3(x, y, z));
            searchStart = match.suffix().first;
        }
    }
    
    // Parse face vertex indices
    std::regex indicesRegex(R"(int\[\]\s+faceVertexIndices\s*=\s*\[([^\]]+)\])");
    if (std::regex_search(content, match, indicesRegex))
    {
        std::vector<int> indices = parseIntArray(match[1].str());
        for (int idx : indices)
        {
            meshData.indices.push_back(static_cast<unsigned int>(idx));
        }
    }
    
    // Parse face vertex counts to triangulate quads
    std::regex countsRegex(R"(int\[\]\s+faceVertexCounts\s*=\s*\[([^\]]+)\])");
    if (std::regex_search(content, match, countsRegex))
    {
        std::vector<int> counts = parseIntArray(match[1].str());
        
        bool hasQuads = false;
        for (int count : counts)
        {
            if (count == 4)
            {
                hasQuads = true;
                break;
            }
        }
        
        if (hasQuads && !meshData.indices.empty())
        {
            std::vector<unsigned int> triangulatedIndices;
            size_t idx = 0;
            
            for (int count : counts)
            {
                if (count == 3)
                {
                    triangulatedIndices.push_back(meshData.indices[idx]);
                    triangulatedIndices.push_back(meshData.indices[idx + 1]);
                    triangulatedIndices.push_back(meshData.indices[idx + 2]);
                    idx += 3;
                }
                else if (count == 4)
                {
                    triangulatedIndices.push_back(meshData.indices[idx]);
                    triangulatedIndices.push_back(meshData.indices[idx + 1]);
                    triangulatedIndices.push_back(meshData.indices[idx + 2]);
                    
                    triangulatedIndices.push_back(meshData.indices[idx]);
                    triangulatedIndices.push_back(meshData.indices[idx + 2]);
                    triangulatedIndices.push_back(meshData.indices[idx + 3]);
                    idx += 4;
                }
                else
                {
                    idx += count;
                }
            }
            
            meshData.indices = triangulatedIndices;
        }
    }
    
    // Parse display color
    std::regex colorRegex(R"(color3f\[\]\s+primvars:displayColor\s*=\s*\[\s*\(\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\)\s*\])");
    if (std::regex_search(content, match, colorRegex))
    {
        meshData.displayColor.r = std::stof(match[1].str());
        meshData.displayColor.g = std::stof(match[2].str());
        meshData.displayColor.b = std::stof(match[3].str());
    }
    
    // Parse physics:collisionEnabled (presence indicates PhysicsCollisionAPI is applied)
    std::regex collisionRegex(R"(bool\s+physics:collisionEnabled\s*=\s*(true|false|1|0))");
    if (std::regex_search(content, match, collisionRegex))
    {
        std::string value = match[1].str();
        meshData.collision = (value == "true" || value == "1");
    }
    
    return !meshData.vertices.empty();
}

std::vector<int> Scene::parseIntArray(const std::string& arrayStr)
{
    std::vector<int> result;
    std::regex numRegex(R"(-?\d+)");
    
    std::string::const_iterator searchStart(arrayStr.cbegin());
    std::smatch match;
    
    while (std::regex_search(searchStart, arrayStr.cend(), match, numRegex))
    {
        result.push_back(std::stoi(match[0].str()));
        searchStart = match.suffix().first;
    }
    
    return result;
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
