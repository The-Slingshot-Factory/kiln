#include "plane_tool.h"
#include <cstring>
#include <string>

// ═══════════════════════════════════════════════════════════════════════════
// PlaneDialog Implementation
// ═══════════════════════════════════════════════════════════════════════════

void PlaneDialog::onOpen()
{
    createdNode = nullptr;
    
    // Generate unique name
    if (currentScene && currentScene->root)
    {
        std::string baseName = "Plane";
        std::string uniqueName = baseName;
        int counter = 1;
        
        while (currentScene->root->findChild(uniqueName))
        {
            uniqueName = baseName + std::to_string(counter++);
        }
        
        std::strncpy(name, uniqueName.c_str(), sizeof(name) - 1);
    }
    else
    {
        std::strcpy(name, "Plane");
    }
    
    size = 10.0f;
    color[0] = 0.6f;
    color[1] = 0.6f;
    color[2] = 0.6f;
    collision = true;
}

void PlaneDialog::renderContent()
{
    ImGui::Text("Create a new plane mesh");
    ImGui::Spacing();
    ImGui::Separator();
    ImGui::Spacing();
    
    // Name
    ImGui::Text("Name:");
    ImGui::SameLine(80);
    ImGui::SetNextItemWidth(-1);
    ImGui::InputText("##PlaneName", name, sizeof(name));
    
    ImGui::Spacing();
    
    // Size
    ImGui::Text("Size:");
    ImGui::SameLine(80);
    ImGui::SetNextItemWidth(-1);
    ImGui::SliderFloat("##PlaneSize", &size, 1.0f, 100.0f, "%.1f units");
    
    ImGui::Spacing();
    
    // Color
    ImGui::Text("Color:");
    ImGui::SameLine(80);
    ImGui::SetNextItemWidth(-1);
    ImGui::ColorEdit3("##PlaneColor", color);
    
    ImGui::Spacing();
    
    // Collision
    ImGui::Text("Physics:");
    ImGui::SameLine(80);
    ImGui::Checkbox("Collision", &collision);
}

bool PlaneDialog::canComplete() const
{
    return std::strlen(name) > 0;
}

void PlaneDialog::onComplete()
{
    if (!currentScene || !currentScene->root) return;
    
    // Ensure uniqueness
    std::string finalName = name;
    std::string baseName = finalName;
    int counter = 1;
    
    while (currentScene->root->findChild(finalName))
    {
        finalName = baseName + std::to_string(counter++);
    }
    
    // Create plane mesh node
    SceneNode* plane = currentScene->root->addChild(finalName, PrimType::Mesh);
    
    float halfSize = size / 2.0f;
    plane->meshData->vertices = {
        glm::vec3(-halfSize, 0, -halfSize),
        glm::vec3( halfSize, 0, -halfSize),
        glm::vec3( halfSize, 0,  halfSize),
        glm::vec3(-halfSize, 0,  halfSize)
    };
    
    plane->meshData->indices = { 0, 1, 2, 0, 2, 3 };
    plane->meshData->displayColor = glm::vec3(color[0], color[1], color[2]);
    plane->meshData->collision = collision;
    
    createdNode = plane;
}

// ═══════════════════════════════════════════════════════════════════════════
// PlaneTool Implementation
// ═══════════════════════════════════════════════════════════════════════════

void PlaneTool::onActivate(Scene* scene)
{
    dialog.setScene(scene);
    dialog.open();
}

SceneNode* PlaneTool::render()
{
    if (dialog.render())
    {
        return dialog.getCreatedNode();
    }
    return nullptr;
}
