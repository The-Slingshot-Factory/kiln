#pragma once

#include "dialog.h"
#include "../../scene/scene.h"
#include <filesystem>
#include <cstring>

class NewSceneDialog : public Dialog
{
public:
    void setLocation(const std::filesystem::path& path, const std::filesystem::path& projectRoot)
    {
        location = path;
        projectPath = projectRoot;
    }
    
    std::filesystem::path getCreatedPath() const { return createdPath; }

protected:
    const char* getTitle() const override { return "Create New Scene"; }
    float getWidth() const override { return 400.0f; }
    
    void onOpen() override
    {
        std::memset(sceneName, 0, sizeof(sceneName));
        std::strcpy(sceneName, "new_scene");
        withGroundPlane = true;
        createdPath.clear();
    }
    
    void renderContent() override
    {
        ImGui::Text("Scene Name:");
        ImGui::SetNextItemWidth(-1);
        ImGui::InputText("##SceneName", sceneName, sizeof(sceneName));
        
        if (ImGui::IsWindowAppearing())
        {
            ImGui::SetKeyboardFocusHere(-1);
        }
        
        ImGui::Spacing();
        
        // Location display
        ImGui::Text("Location:");
        std::string relativePath;
        if (location == projectPath)
        {
            relativePath = projectPath.filename().string() + "/";
        }
        else
        {
            relativePath = std::filesystem::relative(location, projectPath.parent_path()).string() + "/";
        }
        ImGui::TextColored(ImVec4(0.7f, 0.7f, 0.7f, 1.0f), "%s", relativePath.c_str());
        
        ImGui::Spacing();
        ImGui::Separator();
        ImGui::Spacing();
        
        // Scene type
        ImGui::Text("Scene Type:");
        if (ImGui::RadioButton("Empty Scene", !withGroundPlane))
        {
            withGroundPlane = false;
        }
        ImGui::SameLine();
        if (ImGui::RadioButton("With Ground Plane", withGroundPlane))
        {
            withGroundPlane = true;
        }
        
        if (withGroundPlane)
        {
            ImGui::TextColored(ImVec4(0.6f, 0.6f, 0.6f, 1.0f), "Scene will include a ground plane mesh.");
        }
        else
        {
            ImGui::TextColored(ImVec4(0.6f, 0.6f, 0.6f, 1.0f), "Scene will be empty (no meshes).");
        }
    }
    
    bool canComplete() const override
    {
        return std::strlen(sceneName) > 0;
    }
    
    void onComplete() override
    {
        std::string filename = sceneName;
        if (filename.find('.') == std::string::npos)
        {
            filename += ".usda";
        }
        
        std::filesystem::path scenePath = location / filename;
        
        if (std::filesystem::exists(scenePath))
        {
            return;  // Don't overwrite
        }
        
        Scene newScene;
        newScene.name = sceneName;
        newScene.defaultPrim = "World";
        newScene.upAxis = "Y";
        newScene.metersPerUnit = 1.0f;
        
        if (withGroundPlane)
        {
            addGroundPlane(newScene.root.get());
        }
        
        if (newScene.saveToFile(scenePath))
        {
            createdPath = scenePath;
        }
    }

private:
    static void addGroundPlane(SceneNode* parent)
    {
        SceneNode* plane = parent->addChild("GroundPlane", PrimType::Mesh);
        plane->meshData->vertices = {
            glm::vec3(-10, 0, -10),
            glm::vec3( 10, 0, -10),
            glm::vec3( 10, 0,  10),
            glm::vec3(-10, 0,  10)
        };
        plane->meshData->indices = { 0, 1, 2, 0, 2, 3 };
        plane->meshData->displayColor = glm::vec3(0.5f, 0.5f, 0.5f);
        plane->meshData->collision = true;
    }

    std::filesystem::path location;
    std::filesystem::path projectPath;
    std::filesystem::path createdPath;
    char sceneName[256] = "";
    bool withGroundPlane = true;
};

