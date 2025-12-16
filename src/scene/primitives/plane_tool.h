#pragma once

#include "primitive_tool.h"
#include "../../ui/dialogs/dialog.h"
#include <glm/glm.hpp>

class PlaneDialog : public Dialog
{
public:
    void setScene(Scene* scene) { currentScene = scene; }
    SceneNode* getCreatedNode() const { return createdNode; }

protected:
    const char* getTitle() const override { return "New Plane"; }
    
    void onOpen() override;
    void renderContent() override;
    bool canComplete() const override;
    void onComplete() override;

private:
    Scene* currentScene = nullptr;
    SceneNode* createdNode = nullptr;
    
    char name[256] = "Plane";
    float size = 10.0f;
    float color[3] = {0.6f, 0.6f, 0.6f};
    bool collision = true;
};

class PlaneTool : public PrimitiveTool
{
public:
    const char* getName() const override { return "Plane..."; }
    void onActivate(Scene* scene) override;
    SceneNode* render() override;

private:
    PlaneDialog dialog;
};
